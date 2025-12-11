import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from datetime import datetime, date, timedelta
import logging
import contextlib

logger = logging.getLogger(__name__)

# 常數定義
WATER_FEE = 100
PAYMENT_METHODS = ["月繳", "半年繳", "年繳"]

# 輔助函數：生成繳費排程
def generate_payment_schedule(payment_method: str, start_date, end_date):
    """生成繳費排程"""
    try:
        from dateutil.relativedelta import relativedelta
        use_relativedelta = True
    except ImportError:
        use_relativedelta = False
    
    if isinstance(start_date, str):
        start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start = datetime.combine(start_date, datetime.min.time())
    
    if isinstance(end_date, str):
        end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end = datetime.combine(end_date, datetime.min.time())
    
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
                if month == 12:
                    current = datetime(year + 1, 1, 1)
                else:
                    current = datetime(year, month + 1, 1)
        
        elif payment_method == "半年繳":
            if month in [1, 7]:
                schedule.append((year, month))
            if use_relativedelta:
                current = current + relativedelta(months=6)
            else:
                current = current + timedelta(days=180)
        
        elif payment_method == "年繳":
            if month == 1:
                schedule.append((year, month))
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
        pass
    
    @contextlib.contextmanager
    def _get_connection(self):
        try:
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
        """檢查房號是否已存在"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM tenants WHERE room_number=%s AND is_active=1", (room,))
                return cur.fetchone() is not None
    
    def get_tenants(self) -> pd.DataFrame:
        """取得所有房客列表"""
        with self._get_connection() as conn:
            df = pd.read_sql("SELECT * FROM tenants WHERE is_active=1 ORDER BY room_number", conn)
            for col in ['lease_start', 'lease_end', 'created_at']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d')
            return df
    
    def get_tenant_by_id(self, tid: int):
        """根據 ID 取得單一房客"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM tenants WHERE id=%s", (tid,))
                row = cur.fetchone()
                if row:
                    result = dict(row)
                    for k, v in result.items():
                        if isinstance(v, (date, datetime)):
                            result[k] = str(v)
                    return result
        return None
    
    def add_tenant(self, room_number, tenant_name, phone, deposit, base_rent, lease_start, lease_end, payment_method="月繳"):
        """新增房客"""
        try:
            # 轉換日期格式
            if not isinstance(lease_start, str):
                lease_start = lease_start.strftime('%Y-%m-%d')
            if not isinstance(lease_end, str):
                lease_end = lease_end.strftime('%Y-%m-%d')
            
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # 檢查房號是否已存在
                    if self.room_exists(room_number):
                        return False, f"❌ 房號 {room_number} 已存在"
                    
                    # 新增房客
                    cur.execute("""
                        INSERT INTO tenants(
                            room_number, tenant_name, phone, deposit, base_rent,
                            lease_start, lease_end, payment_method,
                            has_discount, has_water_fee, discount_notes,
                            annual_discount_months, annual_discount_amount, last_ac_cleaning_date
                        )
                        VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        room_number, tenant_name, phone, deposit, base_rent,
                        lease_start, lease_end, payment_method,
                        False, False, '', 0, 0, None
                    ))
                    
                    # 自動生成繳費計畫
                    self._generate_payment_schedule_for_tenant(
                        conn, room_number, tenant_name, base_rent, False,
                        payment_method, lease_start, lease_end
                    )
                    
                    return True, f"✅ 房號 {room_number} 已新增"
        
        except Exception as e:
            logger.error(f"Add tenant error: {e}")
            return False, str(e)
    
    def update_tenant(self, room_number, tenant_name=None, phone=None, deposit=None,
                     base_rent=None, lease_start=None, lease_end=None, payment_method=None):
        """編輯房客資訊"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # 先取得現有資料
                    cur.execute("SELECT id FROM tenants WHERE room_number=%s AND is_active=1", (room_number,))
                    result = cur.fetchone()
                    if not result:
                        return False, f"❌ 房號 {room_number} 不存在"
                    
                    tenant_id = result[0]
                    
                    # 轉換日期格式
                    if lease_start and not isinstance(lease_start, str):
                        lease_start = lease_start.strftime('%Y-%m-%d')
                    if lease_end and not isinstance(lease_end, str):
                        lease_end = lease_end.strftime('%Y-%m-%d')
                    
                    # 動態構建 UPDATE 語句
                    updates = []
                    params = []
                    
                    if tenant_name is not None:
                        updates.append("tenant_name=%s")
                        params.append(tenant_name)
                    if phone is not None:
                        updates.append("phone=%s")
                        params.append(phone)
                    if deposit is not None:
                        updates.append("deposit=%s")
                        params.append(deposit)
                    if base_rent is not None:
                        updates.append("base_rent=%s")
                        params.append(base_rent)
                    if lease_start is not None:
                        updates.append("lease_start=%s")
                        params.append(lease_start)
                    if lease_end is not None:
                        updates.append("lease_end=%s")
                        params.append(lease_end)
                    if payment_method is not None:
                        updates.append("payment_method=%s")
                        params.append(payment_method)
                    
                    if updates:
                        params.append(tenant_id)
                        update_sql = f"UPDATE tenants SET {', '.join(updates)} WHERE id=%s"
                        cur.execute(update_sql, tuple(params))
                    
                    return True, f"✅ 房號 {room_number} 已更新"
        
        except Exception as e:
            logger.error(f"Update tenant error: {e}")
            return False, str(e)
    
    def delete_tenant(self, tenant_id: int):
        """刪除房客（軟刪除）"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE tenants SET is_active=0 WHERE id=%s", (tenant_id,))
                    return True, "✅ 已刪除"
        except Exception as e:
            return False, str(e)
    
    def _generate_payment_schedule_for_tenant(self, conn, room: str, tenant_name: str,
                                             base_rent: float, has_water_fee: bool,
                                             payment_method: str, start_date: str, end_date: str):
        """內部方法：生成繳費排程"""
        try:
            amount = base_rent + (WATER_FEE if has_water_fee else 0)
            schedule = generate_payment_schedule(payment_method, start_date, end_date)
            
            with conn.cursor() as cur:
                for year, month in schedule:
                    if month == 12:
                        due_date = f"{year + 1}-01-05"
                    else:
                        due_date = f"{year}-{month + 1:02d}-05"
                    
                    cur.execute("""
                        INSERT INTO payment_schedule(
                            room_number, tenant_name, payment_year, payment_month,
                            amount, payment_method, due_date, status, created_at, updated_at
                        )
                        VALUES(%s, %s, %s, %s, %s, %s, %s, '未繳', NOW(), NOW())
                        ON CONFLICT (room_number, payment_year, payment_month) DO NOTHING
                    """, (room, tenant_name, year, month, amount, payment_method, due_date))
        
        except Exception as e:
            logger.error(f"Schedule Gen Error: {e}")
    
    # ==========================
    # 繳費排程 (Payment Schedule)
    # ==========================
    
    def get_payment_schedule(self, room=None, status=None, year=None) -> pd.DataFrame:
        """取得繳費排程"""
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
        """標記繳費完成"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE payment_schedule
                        SET status='已繳', paid_date=%s, paid_amount=%s, notes=%s, updated_at=NOW()
                        WHERE id=%s
                    """, (paid_date, paid_amount, notes, payment_id))
                    return True, "✅ 繳費已標記"
        except Exception as e:
            return False, str(e)
    
    def get_payment_summary(self, year: int):
        """取得繳費摘要"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT SUM(amount) FROM payment_schedule WHERE payment_year=%s", (year,))
                due = cur.fetchone()[0] or 0
                
                cur.execute("SELECT SUM(paid_amount) FROM payment_schedule WHERE payment_year=%s AND status='已繳'", (year,))
                paid = cur.fetchone()[0] or 0
                
                cur.execute("SELECT COUNT(*) FROM payment_schedule WHERE payment_year=%s AND status='未繳'", (year,))
                unpaid = cur.fetchone()[0] or 0
                
                collection_rate = (paid / due * 100) if due > 0 else 0
                return {
                    'total_due': due,
                    'total_paid': paid,
                    'unpaid_count': unpaid,
                    'collection_rate': collection_rate
                }
    
    def get_overdue_payments(self) -> pd.DataFrame:
        """取得逾期未繳"""
        today = date.today().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            return pd.read_sql("""
                SELECT room_number, tenant_name, payment_month, amount, due_date
                FROM payment_schedule
                WHERE status='未繳' AND due_date < %s
                ORDER BY due_date ASC
            """, conn, params=(today,))
    
    def get_upcoming_payments(self, days_ahead: int = 7) -> pd.DataFrame:
        """取得近期應繳"""
        today = date.today()
        future = today + timedelta(days=days_ahead)
        with self._get_connection() as conn:
            return pd.read_sql("""
                SELECT room_number, tenant_name, payment_month, amount, due_date
                FROM payment_schedule
                WHERE status='未繳' AND due_date >= %s AND due_date <= %s
                ORDER BY due_date ASC
            """, conn, params=(today, future))
    
    # ==========================
    # 租金紀錄 (Rent Records)
    # ==========================
    
    def batch_record_rent(self, room, tenant_name, start_year, start_month, months_count,
                         base_rent, water_fee, discount, payment_method="月繳", notes=""):
        """批量預填租金"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    actual_amount = base_rent + water_fee - discount
                    current_date = date(start_year, start_month, 1)
                    
                    for i in range(months_count):
                        year = current_date.year
                        month = current_date.month
                        
                        cur.execute("""
                            INSERT INTO rent_records(
                                room_number, tenant_name, year, month, base_amount,
                                water_fee, discount_amount, actual_amount, paid_amount,
                                payment_method, notes, status, recorded_by, updated_at
                            )
                            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, '待確認', 'batch', NOW())
                            ON CONFLICT (room_number, year, month) DO UPDATE SET
                            base_amount=EXCLUDED.base_amount, water_fee=EXCLUDED.water_fee,
                            discount_amount=EXCLUDED.discount_amount, actual_amount=EXCLUDED.actual_amount,
                            payment_method=EXCLUDED.payment_method, notes=EXCLUDED.notes, updated_at=NOW()
                        """, (room, tenant_name, year, month, base_rent, water_fee, discount,
                              actual_amount, payment_method, notes))
                        
                        if month == 12:
                            current_date = date(year + 1, 1, 1)
                        else:
                            current_date = date(year, month + 1, 1)
                    
                    return True, f"✅ 已預填 {months_count} 個月租金"
        except Exception as e:
            return False, str(e)
    
    def get_pending_rents(self) -> pd.DataFrame:
        """取得待確認租金"""
        with self._get_connection() as conn:
            return pd.read_sql("""
                SELECT id, room_number, tenant_name, year, month, actual_amount, status
                FROM rent_records WHERE status IN ('待確認', '未收')
                ORDER BY year DESC, month DESC, room_number
            """, conn)
    
    def confirm_rent_payment(self, rent_id, paid_date, paid_amount=None):
        """確認租金已繳"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT actual_amount FROM rent_records WHERE id=%s", (rent_id,))
                    row = cur.fetchone()
                    if not row:
                        return False, "❌ 找不到記錄"
                    
                    actual = row[0]
                    paid_amt = paid_amount if paid_amount is not None else actual
                    
                    cur.execute("""
                        UPDATE rent_records
                        SET status='已收', paid_date=%s, paid_amount=%s, updated_at=NOW()
                        WHERE id=%s
                    """, (paid_date, paid_amt, rent_id))
                    
                    return True, "✅ 租金已確認"
        except Exception as e:
            return False, str(e)
    
    def get_rent_summary(self, year: int):
        """取得租金摘要"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT SUM(actual_amount) FROM rent_records WHERE year=%s", (year,))
                due = cur.fetchone()[0] or 0
                
                cur.execute("SELECT SUM(paid_amount) FROM rent_records WHERE year=%s AND status='已收'", (year,))
                paid = cur.fetchone()[0] or 0
                
                cur.execute("SELECT SUM(actual_amount) FROM rent_records WHERE year=%s AND status IN ('未收', '待確認')", (year,))
                unpaid = cur.fetchone()[0] or 0
                
                collection_rate = (paid / due * 100) if due > 0 else 0
                return {
                    'total_due': due,
                    'total_paid': paid,
                    'total_unpaid': unpaid,
                    'collection_rate': collection_rate
                }
    
    def get_rent_records(self, year=None) -> pd.DataFrame:
        """取得租金記錄"""
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
        """取得租金矩陣"""
        with self._get_connection() as conn:
            df = pd.read_sql("""
                SELECT room_number, month, status, actual_amount
                FROM rent_records WHERE year = %s
                ORDER BY room_number, month
            """, conn, params=(year,))
            
            if df.empty:
                return pd.DataFrame()
            
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
        """取得未繳租金"""
        with self._get_connection() as conn:
            return pd.read_sql("""
                SELECT room_number as "房號", tenant_name as "房客", year as "年", month as "月", actual_amount as "金額"
                FROM rent_records WHERE status IN ('未收', '待確認')
                ORDER BY year DESC, month DESC
            """, conn)
    
    # ==========================
    # 電費管理 (Electricity)
    # ==========================
    
    def add_electricity_period(self, year, ms, me):
        """新增計費期間"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM electricity_period WHERE period_year=%s AND period_month_start=%s AND period_month_end=%s", (year, ms, me))
                    if cur.fetchone():
                        return True, "✅ 期間已存在", 0
                    
                    cur.execute("INSERT INTO electricity_period(period_year, period_month_start, period_month_end) VALUES(%s, %s, %s) RETURNING id", (year, ms, me))
                    new_id = cur.fetchone()[0]
                    return True, "✅ 新增成功", new_id
        except Exception as e:
            return False, str(e), 0
    
    def get_all_periods(self):
        """取得所有計費期間"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM electricity_period ORDER BY id DESC")
                return cur.fetchall()
    
    def add_tdy_bill(self, pid, floor, kwh, fee):
        """新增台電單據"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO electricity_tdy_bill(period_id, floor_name, tdy_total_kwh, tdy_total_fee)
                    VALUES(%s, %s, %s, %s)
                    ON CONFLICT (period_id, floor_name) DO UPDATE SET
                    tdy_total_kwh=EXCLUDED.tdy_total_kwh, tdy_total_fee=EXCLUDED.tdy_total_fee
                """, (pid, floor, kwh, fee))
    
    def add_meter_reading(self, pid, room, start, end):
        """新增電表讀數"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                usage = round(end - start, 2)
                cur.execute("""
                    INSERT INTO electricity_meter(period_id, room_number, meter_start_reading, meter_end_reading, meter_kwh_usage)
                    VALUES(%s, %s, %s, %s, %s)
                    ON CONFLICT (period_id, room_number) DO UPDATE SET
                    meter_start_reading=EXCLUDED.meter_start_reading, meter_end_reading=EXCLUDED.meter_end_reading, meter_kwh_usage=EXCLUDED.meter_kwh_usage
                """, (pid, room, start, end, usage))
    
    def get_period_report(self, pid):
        """取得計費報告"""
        with self._get_connection() as conn:
            return pd.read_sql("""
                SELECT room_number as "房號", private_kwh as "房間度數", public_kwh as "公用分攤",
                total_kwh as "總度數", unit_price as "單價", calculated_fee as "應繳電費"
                FROM electricity_calculation WHERE period_id = %s ORDER BY room_number
            """, conn, params=(pid,))
    
    # ===== 電費繳費記錄方法 (新增) =====
    
    def save_electricity_record(self, period_id, results):
        """
        儲存計費記錄（全部房間的應繳金額）
        
        params:
            period_id: 計費期間 ID
            results: list of dict，包含每個房間的計費資訊
                    [
                        {'房號': '1A', '應繳金額': 2000, ...},
                        ...
                    ]
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    for result in results:
                        room = result.get('房號')
                        fee = int(result.get('應繳金額', 0))
                        
                        cur.execute("""
                            INSERT INTO electricity_payment(period_id, room_number, calculated_fee, status)
                            VALUES(%s, %s, %s, '未繳')
                            ON CONFLICT (period_id, room_number) DO UPDATE SET
                            calculated_fee=EXCLUDED.calculated_fee, updated_at=NOW()
                        """, (period_id, room, fee))
            
            return True, "✅ 計費記錄已儲存到資料庫"
        except Exception as e:
            logger.error(f"Save electricity record error: {e}")
            return False, f"❌ 儲存失敗: {str(e)}"
    
    def get_electricity_payment_record(self, period_id):
        """
        取得某個計費期間的繳費紀錄（用於「計費結果」Tab）
        """
        try:
            with self._get_connection() as conn:
                df = pd.read_sql("""
                    SELECT 
                        room_number as '房號',
                        calculated_fee as '應繳金額',
                        paid_amount as '已繳金額',
                        status as '繳費狀態',
                        payment_date as '繳款日期',
                        notes as '備註',
                        updated_at as '更新時間'
                    FROM electricity_payment 
                    WHERE period_id = %s 
                    ORDER BY room_number
                """, conn, params=(period_id,))
                return df
        except Exception as e:
            logger.error(f"Get electricity payment record error: {e}")
            return pd.DataFrame()
    
    def update_electricity_payment(self, period_id, room_number, status, paid_amount=None, payment_date=None, notes=""):
        """
        更新繳費狀態
        
        params:
            period_id: 計費期間 ID
            room_number: 房號
            status: '未繳', '已繳', '部分繳'
            paid_amount: 已繳金額
            payment_date: 繳款日期 (YYYY-MM-DD)
            notes: 繳費備註
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE electricity_payment 
                        SET status=%s, paid_amount=%s, payment_date=%s, notes=%s, updated_at=NOW()
                        WHERE period_id=%s AND room_number=%s
                    """, (status, paid_amount or 0, payment_date, notes, period_id, room_number))
            
            return True, "✅ 繳費狀態已更新"
        except Exception as e:
            logger.error(f"Update electricity payment error: {e}")
            return False, f"❌ 更新失敗: {str(e)}"
    
    def get_electricity_payment_summary(self, period_id):
        """
        取得某個計費期間的繳費統計
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # 應收總額
                    cur.execute("""
                        SELECT SUM(calculated_fee) FROM electricity_payment WHERE period_id=%s
                    """, (period_id,))
                    total_due = cur.fetchone()[0] or 0
                    
                    # 已繳總額
                    cur.execute("""
                        SELECT SUM(paid_amount) FROM electricity_payment WHERE period_id=%s
                    """, (period_id,))
                    total_paid = cur.fetchone()[0] or 0
                    
                    # 未繳房間數
                    cur.execute("""
                        SELECT COUNT(*) FROM electricity_payment WHERE period_id=%s AND status='未繳'
                    """, (period_id,))
                    unpaid_rooms = cur.fetchone()[0] or 0
                    
                    # 已繳房間數
                    cur.execute("""
                        SELECT COUNT(*) FROM electricity_payment WHERE period_id=%s AND status='已繳'
                    """, (period_id,))
                    paid_rooms = cur.fetchone()[0] or 0
                    
                    # 部分繳房間數
                    cur.execute("""
                        SELECT COUNT(*) FROM electricity_payment WHERE period_id=%s AND status='部分繳'
                    """, (period_id,))
                    partial_rooms = cur.fetchone()[0] or 0
                
                return {
                    'total_due': total_due,
                    'total_paid': total_paid,
                    'total_balance': total_due - total_paid,
                    'paid_rooms': paid_rooms,
                    'unpaid_rooms': unpaid_rooms,
                    'partial_rooms': partial_rooms,
                    'collection_rate': (total_paid / total_due * 100) if total_due > 0 else 0
                }
        except Exception as e:
            logger.error(f"Get electricity payment summary error: {e}")
            return {}
    
    # ==========================
    # 支出 (Expenses)
    # ==========================
    
    def add_expense(self, date, cat, amt, desc):
        """新增支出"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO expenses(expense_date, category, amount, description)
                        VALUES(%s, %s, %s, %s)
                    """, (date, cat, amt, desc))
                    return True
        except Exception as e:
            logger.error(f"Add expense error: {e}")
            return False
    
    def get_expenses(self, limit=50):
        """取得支出列表"""
        with self._get_connection() as conn:
            return pd.read_sql("""
                SELECT * FROM expenses ORDER BY expense_date DESC LIMIT %s
            """, conn, params=(limit,))
    
    # ==========================
    # 備忘錄 (Memos)
    # ==========================
    
    def get_memos(self, completed=False):
        """取得備忘錄"""
        with self._get_connection() as conn:
            return pd.read_sql("""
                SELECT * FROM memos
                WHERE is_completed=%s
                ORDER BY priority DESC, created_at DESC
            """, conn, params=(1 if completed else 0,))
    
    def add_memo(self, text, prio="normal"):
        """新增備忘錄"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO memos(memo_text, priority)
                        VALUES(%s, %s)
                    """, (text, prio))
                    return True
        except Exception as e:
            logger.error(f"Add memo error: {e}")
            return False
    
    def complete_memo(self, mid):
        """完成備忘錄"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE memos SET is_completed=1 WHERE id=%s", (mid,))
                    return True
        except Exception as e:
            logger.error(f"Complete memo error: {e}")
            return False
