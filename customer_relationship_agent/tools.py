import os
import google.cloud.bigquery as bigquery
from google.adk.tools.bigquery.config import BigQueryToolConfig
from google.adk.tools.bigquery.config import WriteMode
from google.adk.tools.bigquery import BigQueryToolset
from google.adk.agents import Agent

# Now add the BigQuery tools and configuration

# Configure BQ connectivity from environment variables
GOOGLE_CLOUD_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "birmiu-agent-one26bir-3066")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "EU")
BQ_DATASET = os.environ.get("BQ_DATASET_NAME", "cymbal_bank")
BQ_CUSTOMER_TABLE = os.environ.get("BQ_CUSTOMER_TABLE", "customers")
BQ_ACCOUNTS_TABLE = os.environ.get("BQ_ACCOUNTS_TABLE", "accounts")
BQ_TRANSACTIONS_TABLE = os.environ.get("BQ_TRANSACTIONS_TABLE", "transactions")

# Ensure the BigQuery tool is read-only
tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)

bigquery_toolset = BigQueryToolset(bigquery_tool_config=tool_config)

# Agent Definition
# The BigQuery tool can only be called as an agent. Use the following to do so.
bigquery_agent = Agent(
    model="gemini-2.5-flash",
    name="bq_agent",
    description=(
        "A read-only agent to answer questions about customer records, accounts, and transactions"
    ),
    instruction=f"""
        You are a data science agent with access to several BigQuery tools to query customer accounts and transactions.

        Make use of those tools to answer the user's questions.

        Use the `cymbal-bank` dataset in the project {GOOGLE_CLOUD_PROJECT_ID}.

        You may query the following tables:
            - accounts
            - customers
            - transactions
    """,
    tools=[bigquery_toolset],
)

def bq_update_customer_phone_number(customer_id: str, new_phone_number: str):
    """
    Updates a customer's phone number
    Args:
        customer_id (str): The ID of the customer.
        new_phone_number (str): The new phone number for this customer
    Output: A confirmation message
    """

    print("Tool 'bq_update_customer_phone_number' called.")

    client = bigquery.Client(project=GOOGLE_CLOUD_PROJECT_ID)
    table_ref = f"{GOOGLE_CLOUD_PROJECT_ID}.{BQ_DATASET}.{BQ_CUSTOMER_TABLE}"

    # 1. Parameterized Update Query
    query = f"""
        UPDATE `{table_ref}`
        SET phone = @new_phone
        WHERE customer_id = @cid
    """

    print(f"Executing query: {query}")

    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("new_phone", "STRING", new_phone_number),
        bigquery.ScalarQueryParameter("cid", "STRING", customer_id)
    ])

    try:
        query_job = client.query(query, job_config=job_config)

        if query_job.num_dml_affected_rows == 0:
            return f"Error: Customer ID {customer_id} not found. No update performed."

        return f"Success: Phone number for Customer {customer_id} updated to {new_phone_number}."

    except Exception as e:
        return f"Error updating record: {str(e)}"


def update_customer_phone_by_name(customer_name: str, new_phone_number: str):
    """
    Updates a customer's phone number by looking up their name.
    Args:
        customer_name (str): The full name of the customer.
        new_phone_number (str): The new phone number for this customer.
    Output: A confirmation or error message.
    """
    print(f"Tool 'update_customer_phone_by_name' called for {customer_name}.")

    client = bigquery.Client(project=GOOGLE_CLOUD_PROJECT_ID)
    table_ref = f"{GOOGLE_CLOUD_PROJECT_ID}.{BQ_DATASET}.{BQ_CUSTOMER_TABLE}"

    # Find the customer_id from the name
    query = f"""
        SELECT customer_id FROM `{table_ref}`
        WHERE name = @name
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("name", "STRING", customer_name)
    ])

    try:
        query_job = client.query(query, job_config=job_config)
        results = list(query_job.result())

        if len(results) == 0:
            return f"Error: Customer '{customer_name}' not found."
        if len(results) > 1:
            return f"Error: Multiple customers found with the name '{customer_name}'. Please provide a unique customer ID."

        customer_id = results[0].customer_id
        print(f"Found customer_id: {customer_id} for name: {customer_name}")

        # Now, call the existing update tool
        return bq_update_customer_phone_number(customer_id, new_phone_number)

    except Exception as e:
        return f"Error looking up customer: {str(e)}"


def find_customer_by_name(customer_name: str):
    """
    Finds a customer's ID by their full name.
    Args:
        customer_name (str): The full name of the customer to find.
    Output: The customer's ID as a string or an error message if not found.
    """
    print(f"Tool 'find_customer_by_name' called for {customer_name}.")

    client = bigquery.Client(project=GOOGLE_CLOUD_PROJECT_ID)
    table_ref = f"{GOOGLE_CLOUD_PROJECT_ID}.{BQ_DATASET}.{BQ_CUSTOMER_TABLE}"

    query = f"SELECT customer_id FROM `{table_ref}` WHERE name = @name"
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("name", "STRING", customer_name)
    ])

    try:
        query_job = client.query(query, job_config=job_config)
        results = list(query_job.result())

        if len(results) == 0:
            return f"Error: Customer '{customer_name}' not found."
        if len(results) > 1:
            return f"Error: Multiple customers found with the name '{customer_name}'. Please use a unique customer ID."

        return results[0].customer_id
    except Exception as e:
        return f"Error finding customer: {str(e)}"

