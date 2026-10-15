-- Demo dataset for BANK_BACKEND=sqlite.
-- Every person, address, merchant and number here is made up. Emails use the reserved example.org domain,
-- phone numbers use Ofcom's 01632 960xxx range set aside for fiction, and the town of Exampleton does not exist.
-- Ceri Jonas and her phone number come from the repo's existing evalset (Google's fictional Cymbal Bank sample),
-- so that the evalset can run against this backend.

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    address TEXT,
    date_joined TEXT
);

CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    account_type TEXT NOT NULL,
    balance REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'GBP',
    opened_date TEXT
);

CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    transaction_date TEXT NOT NULL,
    merchant TEXT NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL
);

CREATE TABLE complaints (
    complaint_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    transaction_id TEXT,
    complaint_date TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    resolution_notes TEXT
);

-- Stand-in for the Google Maps search the navigator uses in the BigQuery setup.
CREATE TABLE advisor_locations (
    place_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    town TEXT NOT NULL,
    opening_hours TEXT
);

INSERT INTO customers VALUES
    ('CUST-1001', 'Alex Example', 'alex.example@example.org', '01632 960 101', '12 Sample Lane, Exampleton, EX1 1AA', '2021-03-14'),
    ('CUST-1002', 'Sam Sample', 'sam.sample@example.org', '01632 960 102', '4 Placeholder Road, Exampleton, EX2 4BB', '2019-11-02'),
    ('CUST-1003', 'Jordan Placeholder', 'jordan.p@example.org', '01632 960 103', '88 Mock Street, Testbury, TB3 8CC', '2022-07-21'),
    ('CUST-1004', 'Priya Testwell', 'priya.testwell@example.org', '01632 960 104', '7 Fixture Close, Testbury, TB1 7DD', '2020-01-09'),
    ('CUST-1005', 'Ceri Jonas', 'ceri_jonas@example.org', '01234 567 890', '3 Stub Avenue, Exampleton, EX3 3EE', '2018-05-30'),
    ('CUST-1006', 'Chris Duplicate', 'chris.d1@example.org', '01632 960 106', '21 Copy Lane, Exampleton, EX4 2FF', '2023-02-11'),
    ('CUST-1007', 'Chris Duplicate', 'chris.d2@example.org', '01632 960 107', '9 Twin Row, Testbury, TB2 9GG', '2024-06-18');

INSERT INTO accounts VALUES
    ('ACC-2001', 'CUST-1001', 'Current', 1342.18, 'GBP', '2021-03-14'),
    ('ACC-2002', 'CUST-1001', 'Savings', 5200.00, 'GBP', '2022-01-05'),
    ('ACC-2003', 'CUST-1002', 'Current', 286.40, 'GBP', '2019-11-02'),
    ('ACC-2004', 'CUST-1003', 'Current', 912.75, 'GBP', '2022-07-21'),
    ('ACC-2005', 'CUST-1004', 'Current', 2104.33, 'GBP', '2020-01-09'),
    ('ACC-2006', 'CUST-1005', 'Current', 640.00, 'GBP', '2018-05-30'),
    ('ACC-2007', 'CUST-1006', 'Current', 75.20, 'GBP', '2023-02-11'),
    ('ACC-2008', 'CUST-1007', 'Current', 431.90, 'GBP', '2024-06-18');

INSERT INTO transactions VALUES
    ('TXN-3001', 'ACC-2001', '2026-09-28', 'Bean There Coffee', 'Eating out', -3.40),
    ('TXN-3002', 'ACC-2001', '2026-09-30', 'Northwind Grocers', 'Groceries', -54.12),
    ('TXN-3003', 'ACC-2001', '2026-10-01', 'Exampleton Rail', 'Transport', -12.80),
    ('TXN-3004', 'ACC-2001', '2026-10-03', 'Gadget Barn', 'Shopping', -89.99),
    ('TXN-3005', 'ACC-2001', '2026-10-03', 'Gadget Barn', 'Shopping', -89.99),
    ('TXN-3006', 'ACC-2001', '2026-10-05', 'StreamBox', 'Subscriptions', -9.99),
    ('TXN-3007', 'ACC-2001', '2026-10-06', 'Acme Payroll', 'Income', 2150.00),
    ('TXN-3008', 'ACC-2003', '2026-10-02', 'Northwind Grocers', 'Groceries', -31.07),
    ('TXN-3009', 'ACC-2003', '2026-10-04', 'Bean There Coffee', 'Eating out', -4.10),
    ('TXN-3010', 'ACC-2004', '2026-09-29', 'Testbury Gym', 'Health', -35.00),
    ('TXN-3011', 'ACC-2004', '2026-10-02', 'StreamBox', 'Subscriptions', -9.99),
    ('TXN-3012', 'ACC-2005', '2026-10-01', 'Testbury Books', 'Shopping', -18.50),
    ('TXN-3013', 'ACC-2006', '2026-10-03', 'Northwind Grocers', 'Groceries', -22.45);

INSERT INTO complaints VALUES
    ('CMP-0001', 'CUST-1003', 'TXN-3011', '2026-10-04', 'Dispute', 'StreamBox charged after the subscription was cancelled on 20 September.', 'Open', NULL),
    ('CMP-0002', 'CUST-1002', NULL, '2026-08-12', 'Service', 'Replacement card arrived two weeks late.', 'Resolved', 'Apologised and confirmed the card is active.');

INSERT INTO advisor_locations VALUES
    ('PLACE-01', 'Pop-Up Advisor at Bean There Coffee, Market Square', '1 Market Square, Exampleton, EX1 2AB', 'Exampleton', 'Mon-Sat 09:00-17:00'),
    ('PLACE-02', 'Pop-Up Advisor at Bean There Coffee, Station Road', '45 Station Road, Exampleton, EX2 5CD', 'Exampleton', 'Mon-Fri 08:00-16:00'),
    ('PLACE-03', 'Pop-Up Advisor at Bean There Coffee, Testbury High Street', '102 High Street, Testbury, TB1 1EF', 'Testbury', 'Tue-Sat 10:00-18:00');
