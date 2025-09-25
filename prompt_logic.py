import ollama
import random
import streamlit as st # Used for st.info and st.code in the placeholder
from pathlib import Path


def build_prompt_from_files(schema_string, examples_file, user_question, num_examples=3):
    """
    Builds a few-shot prompt by randomly selecting a specified
    number of examples from the examples file.
    """
    examples_file = Path(examples_file)

    with examples_file.open('r', encoding="utf-8") as f:
        examples_raw = f.read()

    # Parse all examples into a list
    all_examples = examples_raw.strip().split('###')
    all_examples = [ex.strip() for ex in all_examples if ex.strip()]

    # Randomly select a subset of examples
    if len(all_examples) > num_examples:
        selected_examples = random.sample(all_examples, num_examples)
    else:
        selected_examples = all_examples

    # Format the selected examples
    formatted_examples = ""
    for i, block in enumerate(selected_examples):
        parts = block.strip().split('---')
        question = parts[0].strip()
        query = parts[1].strip()
        
        formatted_examples += f"### Example {i+1}:\n\n**{question}**\n\n**{query}**\n\n"

    # Assemble the final prompt
    prompt = f""""  You are an expert PostgreSQL data analyst and query optimization specialist. Your sole purpose is to convert a business question into a single, high-performance, and syntactically correct PostgreSQL query based on the provided schema and rules.

---
### ## Core Directives
1.  **Output Format:** You MUST respond ONLY with the raw SQL query. Do NOT include markdown code blocks (like ```sql), explanations, or any other text.
2.  **Schema Adherence:** You MUST use ONLY the tables and columns provided in the schema below. Verify that every column you use exists in the specified table. Do not invent or assume any others.
3.  **Error Handling:** If the question cannot be answered with the provided schema, you MUST reply with the exact text: "Error: The question cannot be answered with the available schema."
4.  **Dialect Compliance:** The query MUST be 100% compliant with the PostgreSQL dialect.

---
### ## SQL Logic & Structure Rules
1.  **GROUP BY Rule:** When a `SELECT` statement includes an aggregate function (e.g., `SUM`, `COUNT`) alongside a regular column, that regular column MUST be in the `GROUP BY` clause.
    * **INCORRECT:** `SELECT department, SUM(sales) FROM orders;`
    * **CORRECT:** `SELECT department, SUM(sales) FROM orders GROUP BY department;`

2.  **Filtering Aggregates (`HAVING` Clause):** To filter on the result of an aggregate function (`COUNT()`, `SUM()`, etc.), you MUST use the `HAVING` clause after the `GROUP BY`. You MUST NOT use aggregate functions in the `WHERE` clause.

3.  **Filtering Window Functions (`ROW_NUMBER`)**: To filter on the result of a window function (`ROW_NUMBER()`, `RANK()`, etc.), you MUST first compute it in a Common Table Expression (CTE) or a subquery, and then apply the filter to the result in the outer query.

4.  **Filtering Rows (`WHERE` Clause):** The `WHERE` clause must perfectly match the conditions and timeframes from the user's question. Do not add any "hallucinated" filters that were not requested.

5.  **Cumulative Totals:** Do not calculate a cumulative total (e.g., a running sum) unless the user explicitly asks for it.

6.  **Table Aliases:** Use short, non-reserved words for aliases. Ensure every column in the `GROUP BY` and `ORDER BY` clauses belongs to the correct table alias (e.g., `o.customer_id`).

---
### ## Business Context & Schema

* **Join Key:** The `ssa_category_data` and `ssa_order_data` tables join on `variant_sku` and `sku`.
* **Key Dimensions:** `order_date`, `title`, `customer_type`, `super_category`, `category`, `flavour`.
* **Key Metrics:** `sales_revenue`, `sales_discount`, `order_quantity`.

### Database Schema:
{schema_string}
---
{formatted_examples}
---

### New Task:
**User Question:** {user_question}

**SQL Query:**
"""
    return prompt

def query_olama(prompt):
    """Sends the prompt to a running Olama instance and gets a response."""
    st.info("Sending prompt to Olama...")
    # st.code(prompt, language='text') # Optional: you can hide the full prompt

    try:
        # Make the actual API call to Olama
        response = ollama.generate(
            model='llama3:8b', # Or whichever model you are using
            prompt=prompt,
            options={
            'temperature': 0,
            'seed': 42
        }
        )
        return response['response'].strip()
    except Exception as e:
        st.error(f"Error communicating with Olama: {e}")
        return None