import os
import uuid
from datetime import date
import google.cloud.bigquery as bigquery

# Configure BQ connectivity from environment variables
GOOGLE_CLOUD_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "birmiu-agent-one26bir-3066")
BQ_DATASET = os.environ.get("BQ_DATASET_NAME", "cymbal_bank")
BQ_COMPLAINTS_TABLE = os.environ.get("BQ_COMPLAINTS_TABLE", "complaints")


def create_complaint(customer_id: str, category: str, description: str, transaction_id: str = None):
    """
    Creates a new customer complaint.
    Args:
        customer_id (str): The ID of the customer.
        category (str): The type of issue (e.g., 'Dispute', 'Service', 'Fraud').
        description (str): The user's original complaint text.
        transaction_id (str, optional): The transaction ID if the complaint is about a specific charge.
    Output: The new complaint ID.
    """
    print("Tool 'create_complaint' called.")
    client = bigquery.Client(project=GOOGLE_CLOUD_PROJECT_ID)
    table_ref = f"{GOOGLE_CLOUD_PROJECT_ID}.{BQ_DATASET}.{BQ_COMPLAINTS_TABLE}"

    complaint_id = str(uuid.uuid4())
    complaint_date = date.today().isoformat()

    query = f"""
        INSERT INTO `{table_ref}` (complaint_id, customer_id, transaction_id, complaint_date, category, description, status)
        VALUES (@complaint_id, @customer_id, @transaction_id, @complaint_date, @category, @description, 'Open')
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("complaint_id", "STRING", complaint_id),
        bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id),
        bigquery.ScalarQueryParameter("transaction_id", "STRING", transaction_id),
        bigquery.ScalarQueryParameter("complaint_date", "DATE", complaint_date),
        bigquery.ScalarQueryParameter("category", "STRING", category),
        bigquery.ScalarQueryParameter("description", "STRING", description),
    ])

    try:
        client.query(query, job_config=job_config).result()
        return f"Success: Complaint created with ID: {complaint_id}"
    except Exception as e:
        return f"Error creating complaint: {str(e)}"


def update_complaint(complaint_id: str, status: str = None, resolution_notes: str = None):
    """
    Updates an existing complaint's status or adds resolution notes.
    Args:
        complaint_id (str): The ID of the complaint to update.
        status (str, optional): The new status of the complaint (e.g., 'Pending', 'Resolved').
        resolution_notes (str, optional): Notes to add to the complaint's resolution.
    Output: A confirmation message.
    """
    print("Tool 'update_complaint' called.")

    if not status and not resolution_notes:
        return "Error: You must provide either a new status or resolution notes to update the complaint."

    client = bigquery.Client(project=GOOGLE_CLOUD_PROJECT_ID)
    table_ref = f"{GOOGLE_CLOUD_PROJECT_ID}.{BQ_DATASET}.{BQ_COMPLAINTS_TABLE}"

    set_clauses = []
    params = []

    if status:
        set_clauses.append("status = @status")
        params.append(bigquery.ScalarQueryParameter("status", "STRING", status))
    if resolution_notes:
        set_clauses.append("resolution_notes = @resolution_notes")
        params.append(bigquery.ScalarQueryParameter("resolution_notes", "STRING", resolution_notes))

    params.append(bigquery.ScalarQueryParameter("complaint_id", "STRING", complaint_id))

    query = f"""
        UPDATE `{table_ref}`
        SET {', '.join(set_clauses)}
        WHERE complaint_id = @complaint_id
    """

    job_config = bigquery.QueryJobConfig(query_parameters=params)

    try:
        query_job = client.query(query, job_config=job_config)
        if query_job.num_dml_affected_rows == 0:
            return f"Error: Complaint ID {complaint_id} not found. No update performed."
        return f"Success: Complaint {complaint_id} updated."
    except Exception as e:
        return f"Error updating complaint: {str(e)}"

def initiate_complaint_by_name(customer_name: str, category: str, description: str, transaction_id: str = None):
    """
    Initiates a new customer complaint by looking up the customer's name.
    Args:
        customer_name (str): The full name of the customer.
        category (str): The type of issue (e.g., 'Dispute', 'Service', 'Fraud').
        description (str): The user's original complaint text.
        transaction_id (str, optional): The transaction ID for 'Dispute' category complaints.
    Output: A confirmation message with the new complaint ID or an error message.
    """
    print(f"Tool 'initiate_complaint_by_name' called for {customer_name}.")

    client = bigquery.Client(project=GOOGLE_CLOUD_PROJECT_ID)
    customer_table_ref = f"{GOOGLE_CLOUD_PROJECT_ID}.{BQ_DATASET}.{BQ_CUSTOMER_TABLE}"

    # Step 1: Find the customer_id from the name
    query = f"SELECT customer_id FROM `{customer_table_ref}` WHERE name = @name"
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

        # Step 2: Call the existing create_complaint tool
        return create_complaint(customer_id, category, description, transaction_id)

    except Exception as e:
        return f"Error looking up customer: {str(e)}"

