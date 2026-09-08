-- SQLite; s1 is attached READ ONLY. All monetary sums use integer *_cents.
CREATE TABLE core_orders AS
SELECT o.*, c.customer_state AS state,
 r.review_score, r.review_answer_timestamp, r.review_creation_date,
 strftime('%Y-%m',o.order_purchase_timestamp) AS month
FROM s1.fct_orders o
JOIN s1.dim_customers c USING(customer_id)
LEFT JOIN s1.order_review_summary r USING(order_id)
WHERE o.is_delivered=1
 AND o.order_purchase_timestamp>='2017-01-01 00:00:00'
 AND o.order_purchase_timestamp<'2018-08-01 00:00:00';
CREATE UNIQUE INDEX core_order_pk ON core_orders(order_id);

CREATE TABLE core_items AS
SELECT i.order_id,i.order_item_id,i.seller_id,i.product_id,i.price_cents,i.freight_cents,
 COALESCE(p.product_category_name_english,'PT:'||p.product_category_name,'Unknown') AS category,
 o.month,o.order_purchase_timestamp
FROM s1.fct_order_items i
JOIN core_orders o USING(order_id)
JOIN s1.dim_products p USING(product_id);
CREATE UNIQUE INDEX core_item_pk ON core_items(order_id,order_item_id);

-- One order/category row for CX attribution; category order counts are not additive.
CREATE TABLE order_category AS
SELECT order_id,category,COUNT(*) AS items,SUM(price_cents) AS merchandise_cents,
 SUM(freight_cents) AS freight_cents
FROM core_items GROUP BY order_id,category;

CREATE TABLE marketplace_monthly AS
WITH a AS (
 SELECT month,COUNT(*) AS delivered_orders,COUNT(DISTINCT customer_unique_id) AS unique_customers,
 SUM(merchandise_cents) AS merchandise_cents,SUM(freight_cents) AS freight_cents,
 SUM(payment_cents) AS payment_cents,SUM(item_count) AS items
 FROM core_orders GROUP BY month
), sellers AS (
 SELECT month,COUNT(DISTINCT seller_id) AS active_sellers FROM core_items GROUP BY month
), first_sellers AS (
 SELECT strftime('%Y-%m',first_observed_delivered_order) AS month,COUNT(*) AS new_observed_sellers
 FROM s1.seller_metrics GROUP BY 1
), first_customers AS (
 SELECT strftime('%Y-%m',first_observed_order) AS month,COUNT(*) AS new_observed_customers
 FROM s1.customer_metrics GROUP BY 1
)
SELECT a.*,s.active_sellers,COALESCE(n.new_observed_sellers,0) AS new_observed_sellers,
 COALESCE(c.new_observed_customers,0) AS new_observed_customers
FROM a JOIN sellers s USING(month)
LEFT JOIN first_sellers n USING(month) LEFT JOIN first_customers c USING(month)
ORDER BY month;

CREATE TABLE seller_orders_all AS
SELECT i.seller_id,i.order_id,o.order_status,o.order_purchase_timestamp,
 SUM(i.price_cents) AS merchandise_cents,COUNT(*) AS items
FROM s1.fct_order_items i JOIN s1.fct_orders o USING(order_id)
GROUP BY i.seller_id,i.order_id;
CREATE INDEX seller_order_dates ON seller_orders_all(seller_id,order_purchase_timestamp);

CREATE TABLE seller_activation AS
WITH firsts AS (
 SELECT d.seller_id,
 MIN(CASE WHEN so.order_purchase_timestamp>=d.won_date THEN so.order_purchase_timestamp END) AS first_order_on_or_after_won,
 MIN(CASE WHEN so.order_purchase_timestamp>=d.won_date AND so.order_status='delivered' THEN so.order_purchase_timestamp END) AS first_delivered_order_on_or_after_won,
 COUNT(so.order_id) AS observed_order_count
 FROM s1.fct_closed_deals d LEFT JOIN seller_orders_all so USING(seller_id) GROUP BY d.seller_id
)
SELECT d.mql_id,d.seller_id,l.origin,d.lead_type,d.business_segment,d.won_date,
 f.first_order_on_or_after_won,f.first_delivered_order_on_or_after_won,
 CASE WHEN f.observed_order_count>0 THEN 1 ELSE 0 END AS matched
FROM s1.fct_closed_deals d JOIN firsts f USING(seller_id)
JOIN s1.fct_marketing_leads l USING(mql_id);

-- Full delivered history is used only to identify prior first purchases (left censoring guard).
CREATE TABLE customer_delivered_history AS
SELECT order_id,customer_unique_id,order_purchase_timestamp,merchandise_cents
FROM s1.fct_orders WHERE is_delivered=1 AND order_purchase_timestamp<'2018-08-01 00:00:00';
CREATE INDEX customer_history_dates ON customer_delivered_history(customer_unique_id,order_purchase_timestamp);
