import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from datetime import datetime, date, timedelta
import logging
import contextlib

logger = logging.getLogger(__name__)

# 常數定義 (保留原檔案設定)
WATER_FEE = 100
PAYMENT_METHODS = ["月繳", "半年繳", "年繳"]

# 輔助函數：生成繳費排程 (從原檔案移植)
def generate_payment_schedule(payment_method: str, start_date: str, end_date: str):
    try:
        from dateutil.relativedelta import relativedelta
        use_relativedelta = True
    except ImportError:
        use_relativedelta = False
    
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    schedule = []
    current = start
    
    while current <= end:
        year = current.year
        month = current.month
        
        if payment_method == "月繳":
            schedule.append((year, month))
            if use_relativedelta:
                current = current + relativedelta(months=1)
            else:
                if month == 12: current = datetime(year + 1, 1, 1)
                else: current = datetime(year, month + 1, 1)
        elif payment_method == "半年繳":
            if month in [1, 7]: schedule.append((year, month))
            if use_relativedelta:
                current = current + relativedelta(months=6)
            else:
                current = current + timedelta(days=180) # 簡化
        elif payment_method == "年繳":
            if month == 1: schedule.append((year, month))
            if use_relativedelta:
                current = current + relativedelta(years=1)
            else:
                current = datetime(year + 1, 1, 1)
    return schedule

class SupabaseDB:
    """
    Supabase (PostgreSQL) 版的 RentalDB
    完全相容原 SQLite 版本的介面
    """
    def __init__(self):
        self._init_connection()

    @st.cache_resource
    def _init_connection(_self):
        # 這裡不實際做連線，僅用於依賴管理，連線由 _get_connection 處理
        pass

    @contextlib.contextmanager
    def _get_connection(self):
        try:
            # 從 st.secrets 讀取設定
            conn = psycopg2.connect(**st.secrets["supabase"])
            yield conn
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"DB Connection Error: {e}")
            raise

    # ==========================
    # 房客管理 (Tenants)
    # ==========================
    def room_exists(self, room: str) -> bool:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM tenants WHERE room_number=%s AND is_active=1", (room,))
                return cur.fetchone() is not None

    def get_tenants(self) -> pd.DataFrame:
        with self._get_connection() as conn:
            # 使用 pandas 直接讀取，處理欄位型別
            df = pd.read_sql("SELECT * FROM tenants WHERE is_active=1 ORDER BY room_number", conn)
            # 確保日期欄位為字串格式以配合原 UI
            for col in ['lease_start', 'lease_end', 'created_at']:
                if col in df.columns:
                    df[col] = df[col].astype(str)
            return df

    def get_tenant_by_id(self, tid: int):
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM tenants WHERE id=%s", (tid,))
                row = cur.fetchone()
                if row:
                    # 轉換日期物件為字串
                    for k, v in row.items():
                        if isinstance(v, (date, datetime)):
                            row[k] = str(v)
                    return dict(row)
                return None

    def upsert_tenant(self, room, name, phone, deposit, base_rent, start, end, payment_method="月繳", has_discount=False, has_water_fee=False, discount_notes="", annual_discount_months=0, ac_date=None, tenant_id=None):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    if tenant_id:
                        cur.execute("""
                            UPDATE tenants SET tenant_name=%s, phone=%s, deposit=%s, base_rent=%s, 
                            lease_start=%s, lease_end=%s, payment_method=%s, has_discount=%s, 
                            has_water_fee=%s, discount_notes=%s, annual_discount_months=%s, 
                            annual_discount_amount=0, last_ac_cleaning_date=%s 
                            WHERE id=%s
                        """, (name, phone, deposit, base_rent, start, end, payment_method, 
                              1 if has_discount else 0, 1 if has_water_fee else 0, 
                              discount_notes, annual_discount_months, ac_date, tenant_id))
                        return True, f"✅ 房號 {room} 已更新"
                    else:
                        if self.room_exists(room):
                            return False, f"❌ 房號 {room} 已存在"
                        
                        cur.execute("""
                            INSERT INTO tenants(room_number, tenant_name, phone, deposit, base_rent, lease_start, lease_end, payment_method, has_discount, has_water_fee, discount_notes, annual_discount_months, annual_discount_amount, last_ac_cleaning_date) 
                            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s)
                        """, (room, name, phone, deposit, base_rent, start, end, payment_method, 
                              1 if has_discount else 0, 1 if has_water_fee else 0, 
                              discount_notes, annual_discount_months, ac_date))
                        
                        # 自動生成繳費計畫
                        self._generate_payment_schedule_for_tenant(conn, room, name, base_rent, has_water_fee, payment_method, start, end)
                        return True, f"✅ 房號 {room} 已新增"
        except Exception as e:
            return False, str(e)

    def delete_tenant(self, tid: int):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE tenants SET is_active=0 WHERE id=%s", (tid,))
                return True, "✅ 已刪除"
        except Exception as e:
            return False, str(e)

    def _generate_payment_schedule_for_tenant(self, conn, room: str, tenant_name: str, base_rent: float, has_water_fee: bool, payment_method: str, start_date: str, end_date: str):
        # 內部方法，接收外部傳入的連線以保持交易一致性
        try:
            amount = base_rent + (WATER_FEE if has_water_fee else 0)
            schedule = generate_payment_schedule(payment_method, start_date, end_date)
            with conn.cursor() as cur:
                for year, month in schedule:
                    if month == 12: due_date = f"{year + 1}-01-05"
                    else: due_date = f"{year}-{month + 1:02d}-05"
                    
                    cur.execute("""
                        INSERT INTO payment_schedule (room_number, tenant_name, payment_year, payment_month, amount, payment_method, due_date, status, created_at, updated_at) 
                        VALUES(%s, %s, %s, %s, %s, %s, %s, '未繳', NOW(), NOW())
                        ON CONFLICT (room_number, payment_year, payment_month) DO NOTHING
                    """, (room, tenant_name, year, month, amount, payment_method, due_date))
        except Exception as e:
            logger.error(f"Schedule Gen Error: {e}")

    # ==========================
    # 繳費排程 (Payment Schedule)
    # ==========================
    def get_payment_schedule(self, room=None, status=None, year=None) -> pd.DataFrame:
        with self._get_connection() as conn:
            q = "SELECT * FROM payment_schedule WHERE 1=1"
            params = []
            if room and room != "全部":
                q += " AND room_number=%s"
                params.append(room)
            if status and status != "全部":
                q += " AND status=%s"
                params.append(status)
            if year:
                q += " AND payment_year=%s"
                params.append(year)
            q += " ORDER BY payment_year DESC, payment_month DESC, room_number"
            
            df = pd.read_sql(q, conn, params=tuple(params))
            return df

    def mark_payment_done(self, payment_id: int, paid_date: str, paid_amount: float, notes: str = ""):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE payment_schedule SET status='已繳', paid_date=%s, paid_amount=%s, notes=%s, updated_at=NOW() 
                        WHERE id=%s
                    """, (paid_date, paid_amount, notes, payment_id))
                return True, "✅ 繳費已標記"
        except Exception as e:
            return False, str(e)

    def get_payment_summary(self, year: int):
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT SUM(amount) FROM payment_schedule WHERE payment_year=%s", (year,))
                due = cur.fetchone()[0] or 0
                cur.execute("SELECT SUM(paid_amount) FROM payment_schedule WHERE payment_year=%s AND status='已繳'", (year,))
                paid = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM payment_schedule WHERE payment_year=%s AND status='未繳'", (year,))
                unpaid = cur.fetchone()[0] or 0
                return {'total_due': due, 'total_paid': paid, 'unpaid_count': unpaid, 'collection_rate': (paid/due*100) if due > 0 else 0}

    def get_overdue_payments(self) -> pd.DataFrame:
        today = date.today().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            return pd.read_sql("""SELECT room_number, tenant_name, payment_month, amount, due_date 
                               FROM payment_schedule WHERE status='未繳' AND due_date < %s
                               ORDER BY due_date ASC""", conn, params=(today,))
    
    def get_upcoming_payments(self, days_ahead: int = 7) -> pd.DataFrame:
        today = date.today()
        future = today + timedelta(days=days_ahead)
        with self._get_connection() as conn:
            return pd.read_sql("""SELECT room_number, tenant_name, payment_month, amount, due_date 
                               FROM payment_schedule WHERE status='未繳' AND due_date >= %s AND due_date <= %s
                               ORDER BY due_date ASC""", conn, params=(today, future))

    # ==========================
    # 租金紀錄 (Rent Records)
    # ==========================
    def batch_record_rent(self, room, tenant_name, start_year, start_month, months_count, base_rent, water_fee, discount, payment_method="月繳", notes=""):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    actual_amount = base_rent + water_fee - discount
                    current_date = date(start_year, start_month, 1)
                    
                    for i in range(months_count):
                        year = current_date.year
                        month = current_date.month
                        # 使用 PostgreSQL 的 ON CONFLICT 語法
                        cur.execute("""
                            INSERT INTO rent_records (room_number, tenant_name, year, month, base_amount, water_fee, discount_amount, actual_amount, paid_amount, payment_method, notes, status, recorded_by, updated_at) 
                            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, '待確認', 'batch', NOW())
                            ON CONFLICT (room_number, year, month) DO UPDATE SET
                            base_amount=EXCLUDED.base_amount, water_fee=EXCLUDED.water_fee, 
                            discount_amount=EXCLUDED.discount_amount, actual_amount=EXCLUDED.actual_amount,
                            payment_method=EXCLUDED.payment_method, notes=EXCLUDED.notes, updated_at=NOW()
                        """, (room, tenant_name, year, month, base_rent, water_fee, discount, actual_amount, payment_method, notes))
                        
                        if month == 12: current_date = date(year + 1, 1, 1)
                        else: current_date = date(year, month + 1, 1)
                return True, f"✅ 已預填 {months_count} 個月租金"
        except Exception as e:
            return False, str(e)

    def get_pending_rents(self) -> pd.DataFrame:
        with self._get_connection() as conn:
            return pd.read_sql("""SELECT id, room_number, tenant_name, year, month, actual_amount, status 
                               FROM rent_records WHERE status IN ('待確認', '未收') 
                               ORDER BY year DESC, month DESC, room_number""", conn)

    def confirm_rent_payment(self, rent_id, paid_date, paid_amount=None):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT actual_amount FROM rent_records WHERE id=%s", (rent_id,))
                    row = cur.fetchone()
                    if not row: return False, "❌ 找不到記錄"
                    actual = row[0]
                    paid_amt = paid_amount if paid_amount is not None else actual
                    cur.execute("""
                        UPDATE rent_records SET status='已收', paid_date=%s, paid_amount=%s, updated_at=NOW() WHERE id=%s
                    """, (paid_date, paid_amt, rent_id))
                    return True, "✅ 租金已確認"
        except Exception as e:
            return False, str(e)
            
    def get_rent_summary(self, year: int):
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT SUM(actual_amount) FROM rent_records WHERE year=%s", (year,))
                due = cur.fetchone()[0] or 0
                cur.execute("SELECT SUM(paid_amount) FROM rent_records WHERE year=%s AND status='已收'", (year,))
                paid = cur.fetchone()[0] or 0
                cur.execute("SELECT SUM(actual_amount) FROM rent_records WHERE year=%s AND status IN ('未收', '待確認')", (year,))
                unpaid = cur.fetchone()[0] or 0
                return {'total_due': due, 'total_paid': paid, 'total_unpaid': unpaid, 'collection_rate': (paid/due*100) if due > 0 else 0}

    def get_rent_records(self, year=None) -> pd.DataFrame:
        with self._get_connection() as conn:
            q = "SELECT * FROM rent_records"
            params = []
            if year: 
                q += " WHERE year=%s"
                params.append(year)
            q += " ORDER BY year DESC, month DESC, room_number"
            return pd.read_sql(q, conn, params=tuple(params))

    # ==========================
    # 租金矩陣 (Rent Matrix)
    # ==========================
    def get_rent_matrix(self, year: int) -> pd.DataFrame:
        # 這裡需要特殊的 SQL 處理來模擬原功能
        with self._get_connection() as conn:
            # 優先從 rent_records 抓取 (v13 新邏輯)
            df = pd.read_sql("""
                SELECT room_number, month, status, actual_amount 
                FROM rent_records WHERE year = %s 
                ORDER BY room_number, month
            """, conn, params=(year,))
            
            if df.empty: return pd.DataFrame()
            
            ALL_ROOMS = ["1A", "1B", "2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
            matrix = {r: {m: "" for m in range(1, 13)} for r in ALL_ROOMS}
            
            for _, row in df.iterrows():
                room = row['room_number']
                if room in matrix:
                    if row['status'] == '已收':
                        matrix[room][row['month']] = "✅"
                    else:
                        matrix[room][row['month']] = f"❌ ${int(row['actual_amount'])}"
            
            res = pd.DataFrame.from_dict(matrix, orient='index')
            res.columns = [f"{m}月" for m in range(1, 13)]
            return res

    def get_unpaid_rents(self) -> pd.DataFrame:
        # 從 rent_records 抓未收
        with self._get_connection() as conn:
            return pd.read_sql("""
                SELECT room_number as "房號", tenant_name as "房客", year as "年", month as "月", actual_amount as "金額" 
                FROM rent_records WHERE status IN ('未收', '待確認') ORDER BY year DESC, month DESC
            """, conn)

    # ==========================
    # 電費管理 (Electricity)
    # ==========================
    def add_electricity_period(self, year, ms, me):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM electricity_period WHERE period_year=%s AND period_month_start=%s AND period_month_end=%s", (year, ms, me))
                    if cur.fetchone(): return True, "✅ 期間已存在", 0
                    
                    cur.execute("INSERT INTO electricity_period(period_year, period_month_start, period_month_end) VALUES(%s, %s, %s) RETURNING id", (year, ms, me))
                    new_id = cur.fetchone()[0]
                    return True, "✅ 新增成功", new_id
        except Exception as e:
            return False, str(e), 0

    def get_all_periods(self):
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM electricity_period ORDER BY id DESC")
                return cur.fetchall()

    def add_tdy_bill(self, pid, floor, kwh, fee):
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO electricity_tdy_bill(period_id, floor_name, tdy_total_kwh, tdy_total_fee) 
                    VALUES(%s, %s, %s, %s)
                    ON CONFLICT (period_id, floor_name) DO UPDATE SET 
                    tdy_total_kwh=EXCLUDED.tdy_total_kwh, tdy_total_fee=EXCLUDED.tdy_total_fee
                """, (pid, floor, kwh, fee))

    def add_meter_reading(self, pid, room, start, end):
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                usage = round(end - start, 2)
                cur.execute("""
                    INSERT INTO electricity_meter(period_id, room_number, meter_start_reading, meter_end_reading, meter_kwh_usage) 
                    VALUES(%s, %s, %s, %s, %s)
                    ON CONFLICT (period_id, room_number) DO UPDATE SET
                    meter_start_reading=EXCLUDED.meter_start_reading, meter_end_reading=EXCLUDED.meter_end_reading, meter_kwh_usage=EXCLUDED.meter_kwh_usage
                """, (pid, room, start, end, usage))

    def calculate_electricity_fee(self, pid, calc, meter_data, notes=""):
        try:
            results = []
            SHARING_ROOMS = ["2A", "2B", "3A", "3B", "3C", "3D", "4A", "4B", "4C", "4D"]
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    for room in SHARING_ROOMS:
                        s, e = meter_data[room]
                        if e <= s: continue
                        
                        priv = round(e - s, 2)
                        pub = calc.public_per_room
                        total = round(priv + pub, 2)
                        fee = round(total * calc.unit_price, 0)
                        
                        results.append({
                            '房號': room,
                            '私表度數': f"{priv:.2f}",
                            '分攤度數': str(pub),
                            '合計度數': f"{total:.2f}",
                            '電度單價': f"${calc.unit_price:.4f}/度",
                            '應繳電費': f"${int(fee)}"
                        })
                        
                        cur.execute("""
                            INSERT INTO electricity_calculation(period_id, room_number, private_kwh, public_kwh, total_kwh, unit_price, calculated_fee) 
                            VALUES(%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (period_id, room_number) DO UPDATE SET
                            private_kwh=EXCLUDED.private_kwh, public_kwh=EXCLUDED.public_kwh, total_kwh=EXCLUDED.total_kwh,
                            unit_price=EXCLUDED.unit_price, calculated_fee=EXCLUDED.calculated_fee
                        """, (pid, room, priv, pub, total, calc.unit_price, fee))
                    
                    cur.execute("""
                        UPDATE electricity_period SET unit_price=%s, public_kwh=%s, public_per_room=%s, 
                        tdy_total_kwh=%s, tdy_total_fee=%s, notes=%s WHERE id=%s
                    """, (calc.unit_price, calc.public_kwh, calc.public_per_room, calc.tdy_total_kwh, calc.tdy_total_fee, notes, pid))
            return True, "✅ 計算完成", pd.DataFrame(results)
        except Exception as e:
            return False, str(e), pd.DataFrame()

    def get_period_report(self, pid):
        with self._get_connection() as conn:
            return pd.read_sql("""
                SELECT room_number as "房號", private_kwh as "私表度數", public_kwh as "分攤度數", 
                total_kwh as "合計度數", unit_price as "單價", calculated_fee as "應繳電費" 
                FROM electricity_calculation WHERE period_id = %s ORDER BY room_number
            """, conn, params=(pid,))

    # ==========================
    # 支出 (Expenses)
    # ==========================
    def add_expense(self, date, cat, amt, desc):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO expenses(expense_date, category, amount, description) VALUES(%s, %s, %s, %s)",
                               (date, cat, amt, desc))
                return True
        except Exception as e:
            return False

    def get_expenses(self, limit=50):
        with self._get_connection() as conn:
            return pd.read_sql("SELECT * FROM expenses ORDER BY expense_date DESC LIMIT %s", conn, params=(limit,))

    # ==========================
    # 備忘錄 (Memos)
    # ==========================
    def get_memos(self, completed=False):
        with self._get_connection() as conn:
            return pd.read_sql("SELECT * FROM memos WHERE is_completed=%s ORDER BY priority DESC, created_at DESC", 
                             conn, params=(1 if completed else 0,))

    def add_memo(self, text, prio="normal"):
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO memos(memo_text, priority) VALUES(%s, %s)", (text, prio))
        return True

    def complete_memo(self, mid):
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE memos SET is_completed=1 WHERE id=%s", (mid,))
        return True