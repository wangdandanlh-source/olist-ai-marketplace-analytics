"""Independent read-only QA: reconstruct money from untouched CSVs using Decimal.

Run: python -X utf8 tests/test_session1.py
OLIST_QA_DB lets the build validate interim before publication.
"""
import unittest,sqlite3,csv,json,hashlib,os
from decimal import Decimal
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
class Session1QA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(os.environ.get('OLIST_QA_DB',ROOT/'data/processed/session1.sqlite'))
        cls.db=sqlite3.connect('file:'+cls.path.as_posix()+'?mode=ro',uri=True)
        cls.raw={}
        for key,file in [('orders','olist_orders_dataset.csv'),('customers','olist_customers_dataset.csv'),('items','olist_order_items_dataset.csv'),('payments','olist_order_payments_dataset.csv'),('deals','olist_closed_deals_dataset.csv')]:
            with next((ROOT/'data/raw').rglob(file)).open(encoding='utf-8',newline='') as f: cls.raw[key]=list(csv.DictReader(f))
    @classmethod
    def tearDownClass(cls): cls.db.close()
    def scalar(self,q): return self.db.execute(q).fetchone()[0]
    def test_01_order_customer_keys(self):
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM fct_orders'),len(self.raw['orders']))
        self.assertEqual(self.scalar('SELECT COUNT(DISTINCT order_id) FROM fct_orders'),len(self.raw['orders']))
        self.assertEqual(self.scalar('SELECT COUNT(DISTINCT customer_unique_id) FROM dim_customers'),len({x['customer_unique_id'] for x in self.raw['customers']}))
    def test_02_fact_foreign_keys(self):
        for table in ['fct_order_items','fct_payments','fct_reviews']:
            self.assertEqual(self.scalar(f'SELECT COUNT(*) FROM {table} x LEFT JOIN fct_orders o USING(order_id) WHERE o.order_id IS NULL'),0)
        for fact,dim,key in [('fct_orders','dim_customers','customer_id'),('fct_order_items','dim_products','product_id'),('fct_order_items','dim_sellers','seller_id'),('fct_closed_deals','dim_sellers','seller_id'),('fct_closed_deals','fct_marketing_leads','mql_id')]:
            self.assertEqual(self.scalar(f'SELECT COUNT(*) FROM {fact} f LEFT JOIN {dim} d USING({key}) WHERE d.{key} IS NULL'),0)
    def test_03_decimal_gmv(self):
        total=sum(int(Decimal(x['price'])*100) for x in self.raw['items'])
        self.assertEqual(self.scalar('SELECT SUM(merchandise_cents) FROM fct_orders'),total)
        self.assertEqual(self.scalar('SELECT SUM(price_cents) FROM fct_order_items'),total)
    def test_04_decimal_payment(self):
        total=sum(int(Decimal(x['payment_value'])*100) for x in self.raw['payments'])
        self.assertEqual(self.scalar('SELECT SUM(payment_cents) FROM fct_orders'),total)
    def test_05_decimal_freight(self):
        total=sum(int(Decimal(x['freight_value'])*100) for x in self.raw['items'])
        self.assertEqual(self.scalar('SELECT SUM(freight_cents) FROM fct_orders'),total)
    def test_06_delivered_metric_reconciliation(self):
        eligible={x['order_id'] for x in self.raw['orders'] if x['order_status']=='delivered'}
        total=sum(int(Decimal(x['price'])*100) for x in self.raw['items'] if x['order_id'] in eligible)
        for table in ['monthly_marketplace_metrics','customer_metrics','seller_metrics','category_metrics']:
            self.assertEqual(self.scalar(f'SELECT SUM(merchandise_cents) FROM {table}'),total)
    def test_07_order_level_no_inflation(self):
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM fct_orders'),self.scalar('SELECT COUNT(DISTINCT order_id) FROM fct_orders'))
        actual=self.db.execute('SELECT order_id,COUNT(*) FROM fct_order_items GROUP BY order_id').fetchall()
        modeled=dict(self.db.execute('SELECT order_id,item_count FROM fct_orders WHERE has_items=1'))
        self.assertEqual(dict(actual),modeled)
    def test_08_review_choice_and_cardinality(self):
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM order_review_summary'),self.scalar('SELECT COUNT(DISTINCT order_id) FROM fct_reviews'))
        mismatch=self.scalar('''WITH ranked AS (SELECT review_row_id,ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY review_answer_timestamp DESC,review_creation_date DESC,review_id DESC,review_row_id DESC) rn FROM fct_reviews) SELECT COUNT(*) FROM order_review_summary s LEFT JOIN ranked r ON s.review_row_id=r.review_row_id AND r.rn=1 WHERE r.review_row_id IS NULL''')
        self.assertEqual(mismatch,0)
    def test_09_seller_funnel_intersection(self):
        known={x['seller_id'] for x in self.raw['items']}; deals={x['seller_id'] for x in self.raw['deals']}; expected=len(known&deals)
        self.assertEqual(expected,380)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM fct_closed_deals d WHERE EXISTS(SELECT 1 FROM fct_order_items i WHERE i.seller_id=d.seller_id)'),expected)
    def test_10_dates_and_month_sort(self):
        values=[x[0] for x in self.db.execute('SELECT order_purchase_timestamp FROM fct_orders')]
        parsed=[datetime.strptime(x,'%Y-%m-%d %H:%M:%S') for x in values]
        self.assertLess(min(parsed),max(parsed)); self.assertGreater(len({x.strftime('%Y-%m') for x in parsed}),1)
        months=[x[0] for x in self.db.execute('SELECT month FROM monthly_marketplace_metrics ORDER BY month')]
        self.assertEqual(months,sorted(months,key=lambda x:datetime.strptime(x,'%Y-%m')))
        for table in ['fct_orders','fct_order_items','fct_reviews','fct_closed_deals','fct_marketing_leads']:
            columns=[r[1] for r in self.db.execute(f'PRAGMA table_info({table})')]
            for col in columns:
                if col in ['order_purchase_timestamp','order_approved_at','order_delivered_carrier_date','order_delivered_customer_date','order_estimated_delivery_date','shipping_limit_date','review_creation_date','review_answer_timestamp','won_date','first_contact_date']:
                    for row in self.db.execute(f'SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL'): datetime.strptime(row[0],'%Y-%m-%d %H:%M:%S')
    def test_11_money_nonnegative(self):
        for table,col in [('fct_order_items','price_cents'),('fct_order_items','freight_cents'),('fct_payments','payment_cents')]: self.assertEqual(self.scalar(f'SELECT COUNT(*) FROM {table} WHERE {col}<0 OR {col} IS NULL'),0)
    def test_12_fulfillment_denominators(self):
        self.assertEqual(self.scalar('SELECT SUM(late_eligible_orders) FROM fulfillment_metrics'),self.scalar('SELECT COUNT(is_late) FROM fct_orders WHERE is_delivered=1'))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM fct_orders WHERE is_late IS NOT NULL AND (delivery_days IS NULL OR is_delivered=0)'),0)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM fct_orders WHERE is_late=1 AND date(order_delivered_customer_date)<=date(order_estimated_delivery_date)'),0)
    def test_13_raw_checksums(self):
        with (ROOT/'outputs/data_manifest.csv').open(encoding='utf-8-sig') as f:
            for row in csv.DictReader(f): self.assertEqual(hashlib.sha256((ROOT/'data/raw'/row['dataset']/row['filename']).read_bytes()).hexdigest(),row['sha256'])
    def test_14_export_integrity(self):
        for file in self.path.parent.glob('*.csv'):
            with file.open(encoding='utf-8-sig',newline='') as f:
                reader=csv.reader(f); next(reader); count=sum(1 for _ in reader)
            self.assertEqual(count,self.scalar('SELECT COUNT(*) FROM '+file.stem))
    def test_15_geolocation_unique(self):
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM dim_geolocation_prefix'),self.scalar('SELECT COUNT(DISTINCT geolocation_zip_code_prefix) FROM dim_geolocation_prefix'))
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM dim_customers c LEFT JOIN dim_geolocation_prefix g ON c.customer_zip_code_prefix=g.geolocation_zip_code_prefix'),len(self.raw['customers']))
    def test_16_difference_not_silently_fixed(self):
        self.assertGreater(self.scalar('SELECT COUNT(*) FROM fct_orders WHERE ABS(payment_cents-merchandise_cents-freight_cents)>1'),0)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM fct_orders WHERE ABS(payment_cents-merchandise_cents-freight_cents)>1'),303)
    def test_17_funnel_full_preservation(self):
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM fct_marketing_leads'),8000)
        self.assertEqual(self.scalar('SELECT SUM(is_closed) FROM fct_marketing_leads'),842)
        self.assertEqual(self.scalar('SELECT SUM(closed_deals) FROM seller_funnel_metrics'),842)
    def test_18_customer_repeat_reconstruction(self):
        ids={x['customer_id']:x['customer_unique_id'] for x in self.raw['customers']}; counts={}
        for row in self.raw['orders']:
            if row['order_status']=='delivered': counts[ids[row['customer_id']]]=counts.get(ids[row['customer_id']],0)+1
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM customer_metrics WHERE delivered_orders>=2'),sum(v>=2 for v in counts.values()))
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Session1QA)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (ROOT/'outputs/independent_test_summary.json').write_text(json.dumps({'tests_run':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors),'failed':len(result.failures),'errors':len(result.errors)},indent=2),encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
