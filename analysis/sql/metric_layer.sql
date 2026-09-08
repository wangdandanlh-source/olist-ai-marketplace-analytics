-- SQLite. Run by src/build.py against validated staging facts.
-- Monetary columns are integer BRL cents; never sum money after joining child facts.
CREATE TABLE monthly_marketplace_metrics AS
SELECT strftime('%Y-%m',order_purchase_timestamp) AS month,
 COUNT(*) AS all_orders,
 SUM(is_delivered) AS delivered_orders,
 COUNT(DISTINCT CASE WHEN is_delivered=1 THEN customer_unique_id END) AS unique_customers,
 SUM(CASE WHEN is_delivered=1 THEN merchandise_cents ELSE 0 END) AS merchandise_cents,
 SUM(CASE WHEN is_delivered=1 THEN freight_cents ELSE 0 END) AS freight_cents,
 SUM(CASE WHEN is_delivered=1 THEN payment_cents ELSE 0 END) AS payment_cents,
 SUM(CASE WHEN is_delivered=1 THEN item_count ELSE 0 END) AS items_sold,
 SUM(CASE WHEN is_delivered=1 THEN merchandise_cents ELSE 0 END)*1.0/NULLIF(SUM(is_delivered),0) AS aov_cents,
 CASE WHEN strftime('%Y-%m',order_purchase_timestamp) BETWEEN '2017-01' AND '2018-07' THEN 1 ELSE 0 END AS core_month
FROM fct_orders GROUP BY 1 ORDER BY 1;

CREATE TABLE customer_metrics AS
SELECT customer_unique_id, COUNT(*) AS delivered_orders,
 MIN(order_purchase_timestamp) AS first_observed_order,
 MAX(order_purchase_timestamp) AS last_observed_order,
 SUM(merchandise_cents) AS merchandise_cents
FROM fct_orders WHERE is_delivered=1 GROUP BY customer_unique_id;

CREATE TABLE seller_metrics AS
SELECT i.seller_id, COUNT(DISTINCT i.order_id) AS delivered_orders,
 COUNT(*) AS items_sold, SUM(i.price_cents) AS merchandise_cents,
 MIN(o.order_purchase_timestamp) AS first_observed_delivered_order
FROM fct_order_items i JOIN fct_orders o USING(order_id)
WHERE o.is_delivered=1 GROUP BY i.seller_id;

CREATE TABLE category_metrics AS
SELECT strftime('%Y-%m',o.order_purchase_timestamp) AS month,
 COALESCE(p.product_category_name,'__missing__') AS category,
 COUNT(DISTINCT i.order_id) AS delivered_orders, COUNT(*) AS items_sold,
 SUM(i.price_cents) AS merchandise_cents, SUM(i.freight_cents) AS freight_cents
FROM fct_order_items i JOIN fct_orders o USING(order_id)
JOIN dim_products p USING(product_id)
WHERE o.is_delivered=1 GROUP BY 1,2 ORDER BY 1,2;

CREATE TABLE review_metrics AS
SELECT strftime('%Y-%m',o.order_purchase_timestamp) AS month,
 COUNT(*) AS reviewed_orders, AVG(r.review_score) AS average_review_score,
 SUM(CASE WHEN r.review_score<=2 THEN 1 ELSE 0 END) AS low_rating_orders,
 SUM(CASE WHEN r.review_score<=2 THEN 1.0 ELSE 0 END)/COUNT(*) AS low_rating_rate
FROM order_review_summary r JOIN fct_orders o USING(order_id)
WHERE o.is_delivered=1 GROUP BY 1 ORDER BY 1;

CREATE TABLE fulfillment_metrics AS
SELECT strftime('%Y-%m',order_purchase_timestamp) AS month,
 COUNT(*) AS delivered_orders, COUNT(delivery_days) AS delivery_eligible_orders,
 AVG(delivery_days) AS average_delivery_days,
 COUNT(is_late) AS late_eligible_orders, SUM(is_late) AS late_orders,
 SUM(is_late)*1.0/NULLIF(COUNT(is_late),0) AS late_delivery_rate,
 AVG(estimated_gap_days) AS average_estimated_gap_days
FROM fct_orders WHERE is_delivered=1 GROUP BY 1 ORDER BY 1;

CREATE TABLE seller_funnel_metrics AS
SELECT strftime('%Y-%m',first_contact_date) AS contact_month,
 COALESCE(origin,'__missing__') AS origin, COUNT(*) AS mql,
 SUM(is_closed) AS closed_deals,
 SUM(is_closed)*1.0/COUNT(*) AS observed_conversion_rate,
 AVG(time_to_close_days) AS average_time_to_close_days
FROM fct_marketing_leads GROUP BY 1,2 ORDER BY 1,2;
