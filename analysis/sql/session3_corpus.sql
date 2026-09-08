-- All source tables are Session1 processed, attached as s1 READ ONLY.
-- One canonical review per order; category is an exclusive order-level group.
WITH category_distinct AS (
 SELECT DISTINCT i.order_id,COALESCE(p.product_category_name_english,'PT:'||p.product_category_name,'Unknown') AS category
 FROM s1.fct_order_items i JOIN s1.dim_products p USING(product_id)
), category_order AS (
 SELECT order_id,CASE WHEN COUNT(*)>1 THEN 'Multi-category' ELSE MIN(category) END AS category
 FROM category_distinct GROUP BY order_id
)
SELECT r.review_row_id,r.review_id,r.order_id,r.review_score,r.review_comment_message AS review_text_raw,
 r.review_answer_timestamp,r.review_creation_date,o.order_status,o.order_purchase_timestamp,
 o.order_delivered_customer_date,o.is_late,o.estimated_gap_days AS delay_days,o.delivery_days,
 o.merchandise_cents,o.customer_unique_id,c.customer_state,COALESCE(k.category,'Unknown') AS category,
 strftime('%Y-%m',o.order_purchase_timestamp) AS purchase_month
FROM s1.order_review_summary r JOIN s1.fct_orders o USING(order_id)
JOIN s1.dim_customers c USING(customer_id) LEFT JOIN category_order k USING(order_id);
