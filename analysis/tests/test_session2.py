"""Independent Session2 read-only SQL verification. Never opens raw data."""
from pathlib import Path
import sqlite3,unittest,os,json,csv,hashlib
ROOT=Path(__file__).resolve().parents[1]
class Session2QA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=Path(os.environ.get('OLIST_S2_QA_DB',ROOT/'data/processed/session2.sqlite'))
        cls.db=sqlite3.connect('file:'+p.as_posix()+'?mode=ro',uri=True)
        cls.db.execute('ATTACH DATABASE ? AS s1',('file:'+(ROOT/'data/processed/session1.sqlite').as_posix()+'?mode=ro',))
    @classmethod
    def tearDownClass(cls):cls.db.close()
    def v(self,q):return self.db.execute(q).fetchone()[0]
    def test_01_core_filter(self):
        self.assertEqual(self.v("SELECT COUNT(*) FROM core_orders WHERE order_purchase_timestamp<'2017-01-01' OR order_purchase_timestamp>='2018-08-01' OR is_delivered<>1"),0)
        self.assertEqual(self.v('SELECT COUNT(*) FROM core_orders'),self.v("SELECT COUNT(*) FROM s1.fct_orders WHERE is_delivered=1 AND order_purchase_timestamp>='2017-01-01' AND order_purchase_timestamp<'2018-08-01'"))
    def test_02_money_integer_and_consistent(self):
        self.assertEqual(self.v("SELECT COUNT(*) FROM core_items WHERE typeof(price_cents)<>'integer'"),0)
        for col in ['merchandise_cents','freight_cents','payment_cents']:
            self.assertEqual(self.v(f'SELECT SUM({col}) FROM core_orders'),self.v(f"SELECT SUM({col}) FROM s1.monthly_marketplace_metrics WHERE month BETWEEN '2017-01' AND '2018-07'"))
    def test_03_contiguous_months(self):
        months=[x[0] for x in self.db.execute('SELECT month FROM s2_marketplace_monthly ORDER BY month')]
        expected=[f'{y}-{m:02d}' for y in [2017,2018] for m in range(1,13) if y==2017 or m<=7]
        self.assertEqual(months,expected)
    def test_04_no_join_explosion(self):
        self.assertEqual(self.v('SELECT COUNT(*) FROM core_orders'),self.v('SELECT COUNT(DISTINCT order_id) FROM core_orders'))
        self.assertEqual(self.v('SELECT SUM(price_cents) FROM core_items'),self.v('SELECT SUM(merchandise_cents) FROM core_orders'))
        self.assertEqual(self.v('SELECT SUM(merchandise_cents) FROM order_category'),self.v('SELECT SUM(price_cents) FROM core_items'))
    def test_05_delivered_activation_minimum(self):
        self.assertEqual(self.v('''SELECT COUNT(*) FROM seller_activation a WHERE a.first_delivered_order_on_or_after_won IS NOT
          (SELECT MIN(o.order_purchase_timestamp) FROM seller_orders_all o WHERE o.seller_id=a.seller_id AND o.order_status='delivered' AND o.order_purchase_timestamp>=a.won_date)'''),0)
    def test_06_seller_windows(self):
        self.assertEqual(self.v("SELECT COUNT(*) FROM s2_seller_postdeal WHERE window_end>'2018-08-01 00:00:00' OR activation_date<'2017-01-01'"),0)
        self.assertEqual(self.v('SELECT COUNT(*) FROM s2_seller_postdeal p JOIN seller_activation a USING(seller_id) WHERE a.matched<>1'),0)
        self.assertEqual(self.v("SELECT COUNT(*) FROM s2_seller_postdeal WHERE ABS(julianday(window_end)-julianday(activation_date)-days)>0.00001"),0)
    def test_07_seller_outcomes_independent(self):
        self.assertEqual(self.v('''SELECT COUNT(*) FROM s2_seller_postdeal p WHERE p.merchandise_cents <> COALESCE((SELECT SUM(o.merchandise_cents) FROM seller_orders_all o WHERE o.seller_id=p.seller_id AND o.order_status='delivered' AND o.order_purchase_timestamp>=p.activation_date AND o.order_purchase_timestamp<p.window_end),0)'''),0)
        self.assertEqual(self.v('''SELECT COUNT(*) FROM s2_seller_postdeal p WHERE p.orders <> (SELECT COUNT(*) FROM seller_orders_all o WHERE o.seller_id=p.seller_id AND o.order_status='delivered' AND o.order_purchase_timestamp>=p.activation_date AND o.order_purchase_timestamp<p.window_end)'''),0)
    def test_08_common90(self):
        ids=[{x[0] for x in self.db.execute(f'SELECT seller_id FROM s2_seller_postdeal WHERE common90=1 AND days={d}')} for d in [30,60,90]]
        self.assertEqual(ids[0],ids[1]);self.assertEqual(ids[1],ids[2]);self.assertGreater(len(ids[0]),0)
    def test_09_customer_identity(self):
        self.assertEqual(self.v('SELECT COUNT(*) FROM customer_level'),self.v('SELECT COUNT(DISTINCT customer_unique_id) FROM core_orders'))
        self.assertEqual(self.v('SELECT SUM(orders) FROM customer_level'),self.v('SELECT COUNT(*) FROM core_orders'))
    def test_10_cohort_first_purchase(self):
        self.assertEqual(self.v('''WITH firsts AS (SELECT customer_unique_id,MIN(order_purchase_timestamp) first_at FROM customer_delivered_history GROUP BY customer_unique_id) SELECT COUNT(*) FROM customer_cohort_members c JOIN firsts f USING(customer_unique_id) WHERE c.first_purchase<>f.first_at'''),0)
    def test_11_cohort_maturity_and_nulls(self):
        self.assertEqual(self.v("SELECT COUNT(*) FROM s2_customer_cohort WHERE fully_mature_cohort=1 AND latest_possible_window_end>'2018-08-01 00:00:00'"),0)
        self.assertEqual(self.v('SELECT COUNT(*) FROM s2_customer_cohort WHERE fully_mature_cohort=0 AND (repurchase_rate IS NOT NULL OR sample_size<>0)'),0)
    def test_12_repurchase_independent(self):
        for d in [30,60,90]:
            actual=self.v(f'SELECT SUM(repurchase_{d}d) FROM customer_cohort_members WHERE mature_{d}d=1')
            expected=self.v(f'''SELECT COUNT(DISTINCT c.customer_unique_id) FROM customer_cohort_members c JOIN customer_delivered_history h USING(customer_unique_id) WHERE c.mature_{d}d=1 AND h.order_purchase_timestamp>c.first_purchase AND julianday(h.order_purchase_timestamp)-julianday(c.first_purchase)<{d}''')
            self.assertEqual(actual,expected)
    def test_13_review_and_late_denominator(self):
        self.assertEqual(self.v('SELECT COUNT(*) FROM cx_order_sample'),self.v('SELECT COUNT(DISTINCT order_id) FROM cx_order_sample'))
        self.assertEqual(self.v('SELECT COUNT(*) FROM cx_order_sample'),self.v('SELECT COUNT(*) FROM core_orders WHERE is_late IS NOT NULL AND review_score IS NOT NULL'))
        self.assertEqual(self.v("SELECT SUM(sample_size) FROM s2_fulfillment_cx WHERE dimension='is_late'"),self.v('SELECT COUNT(is_late) FROM core_orders'))
    def test_14_category_orders_and_money(self):
        self.assertEqual(self.v('SELECT SUM(merchandise_cents) FROM s2_category_analysis'),self.v('SELECT SUM(merchandise_cents) FROM core_orders'))
        self.assertEqual(self.v('SELECT COUNT(*) FROM order_category'),self.v('SELECT SUM(orders) FROM s2_category_analysis'))
    def test_15_funnel_not_false_conversion(self):
        self.assertEqual(self.v("SELECT SUM(mql) FROM s2_funnel_analysis WHERE dimension='origin'"),8000)
        self.assertEqual(self.v("SELECT SUM(closed_deals) FROM s2_funnel_analysis WHERE dimension='origin'"),842)
        self.assertEqual(self.v("SELECT COUNT(*) FROM s2_funnel_analysis WHERE dimension IN ('lead_type','business_segment') AND observed_conversion IS NOT NULL"),0)
    def test_16_match_bias_denominators(self):
        for dimension in ['origin','lead_type','business_segment','won_month']:
            self.assertEqual(self.v(f"SELECT SUM(closed_deals) FROM s2_seller_match_bias WHERE dimension='{dimension}'"),842)
            self.assertEqual(self.v(f"SELECT SUM(matched_sellers) FROM s2_seller_match_bias WHERE dimension='{dimension}'"),380)
    def test_17_statistical_samples(self):
        self.assertEqual(self.v("SELECT N FROM s2_statistical_tests WHERE test_id='late_review_score'"),self.v('SELECT COUNT(*) FROM cx_order_sample'))
        self.assertEqual(self.v("SELECT N FROM s2_statistical_tests WHERE test_id='origin_observed_conversion'"),8000)
        self.assertEqual(self.v("SELECT COUNT(*) FROM s2_statistical_tests WHERE p_value<0 OR p_value>1 OR q_value_bh<0 OR q_value_bh>1 OR N<=0"),0)
    def test_18_reconciliation_missing_leg(self):
        self.assertEqual(self.v("SELECT sample_size FROM s2_delivered_reconciliation WHERE scope='all_delivered' AND [group]='total'"),self.v('SELECT COUNT(*) FROM s1.fct_orders WHERE is_delivered=1'))
        self.assertEqual(self.v("SELECT payment_cents FROM s2_delivered_reconciliation WHERE scope='all_delivered' AND [group]='total'"),self.v('SELECT SUM(payment_cents) FROM s1.fct_orders WHERE is_delivered=1'))
    def test_19_fixed_window_funnel(self):
        for days in [30,60,90]:
            got=self.v(f"SELECT SUM(closed_{days}d) FROM s2_funnel_analysis WHERE dimension='origin'")
            expected=self.v(f'''SELECT COUNT(*) FROM s1.fct_marketing_leads WHERE won_date>=first_contact_date AND julianday(won_date)-julianday(first_contact_date)<{days} AND datetime(first_contact_date,'+{days} days')<='2018-08-01 00:00:00' ''')
            self.assertEqual(got,expected)
    def test_20_csv_matches_db(self):
        for (table,) in self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 's2_%'"):
            p=ROOT/'outputs'/('session2_'+table[3:]+'.csv')
            with p.open(encoding='utf-8-sig',newline='') as f:count=sum(1 for _ in csv.DictReader(f))
            self.assertEqual(count,self.v('SELECT COUNT(*) FROM '+table))
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Session2QA);result=unittest.TextTestRunner(verbosity=2).run(suite)
    (ROOT/'outputs/session2_independent_test_summary.json').write_text(json.dumps(dict(tests_run=result.testsRun,passed=result.testsRun-len(result.failures)-len(result.errors),failed=len(result.failures),errors=len(result.errors)),indent=2),encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
