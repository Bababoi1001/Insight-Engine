# Database Schema Documentation

This document describes the tables and columns in the database. The goal is to provide context for an AI to generate accurate SQL queries.

## Table Relationships
- The `ssa_order_data` table can be joined with `ssa_category_data` using the SKU columns: `ssa_order_data.sku = ssa_category_data.variant_sku`.

---

## Table: ssa_category_data
**Description**: This is a product dimension table. It contains detailed information and classifications for each product variant sold.

- **column**: `variant_sku` (VARCHAR)
  - **description**: The unique Stock Keeping Unit (SKU) for a specific product variant. This is the primary identifier for a product and is used to join with the orders table.
  - **aliases**: "product id", "sku"

- **column**: `super_category` (VARCHAR)
  - **description**: The highest-level product category (e.g., 'Beverages', 'Snacks').
  - **aliases**: "main category", "product line"

- **column**: `category` (VARCHAR)
  - **description**: The main product category, which is a sub-group of the super_category (e.g., 'Carbonated Drinks', 'Chips').

- **column**: `flavour` (VARCHAR)
  - **description**: The specific flavor of the product (e.g., 'Cola', 'Orange', 'Cheese').
  - **aliases**: "taste"

- **column**: `variant` (VARCHAR)
  - **description**: Describes the specific packaging or size of the product (e.g., '250ml Can', '500g Bag').
  - **aliases**: "size", "packaging type"

- **column**: `mrp` (INTEGER)
  - **description**: The Maximum Retail Price of the product before any discounts are applied.
  - **aliases**: "price", "list price", "cost", "sticker price"

---

## Table: ssa_order_data
**Description**: This is a sales transaction table. Each row represents a specific product line item within a customer's order.

- **column**: `order_date` (DATE)
  - **description**: The date on which the customer placed the order.
  - **aliases**: "when the order was placed", "sale date", "purchase date"

- **column**: `order_id` (BIGINT)
  - **description**: A unique identifier for each distinct customer order. Multiple rows can share the same order_id if the order contained multiple products.
  - **aliases**: "order number"

- **column**: `order_name` (VARCHAR)
  - **description**: The name or reference number of the order, which might be a human-readable version of the order_id.

- **column**: `customer_id` (BIGINT)
  - **description**: A unique identifier for each customer.

- **column**: `customer_type` (VARCHAR)
  - **description**: Classifies the customer (e.g., 'New', 'Returning', 'Wholesale').

- **column**: `billing_state` (VARCHAR)
  - **description**: The state or province in the customer's billing address.
  - **aliases**: "location", "state", "region"

- **column**: `sku` (VARCHAR)
  - **description**: The SKU of the product sold in this order line item. This is the foreign key that links to `ssa_category_data.variant_sku`.
  - **aliases**: "product id"

- **column**: `title` (VARCHAR)
  - **description**: The main title or name of the product.

- **column**: `varianttitle` (VARCHAR)
  - **description**: The full descriptive title of the product variant, often a combination of title and variant.

- **column**: `sales_revenue` (BIGINT)
  - **description**: The total revenue generated from this line item after discounts. This is a key financial metric.
  - **aliases**: "revenue", "sales", "income", "total sales"

- **column**: `sales_discount` (REAL)
  - **description**: The value of the discount applied to this line item.
  - **aliases**: "discount"

- **column**: `order_quantity` (BIGINT)
  - **description**: The number of units of this specific product (SKU) sold in this order.
  - **aliases**: "quantity", "units sold", "how many were sold"