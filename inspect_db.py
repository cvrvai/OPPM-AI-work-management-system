import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='oppm', user='oppm', password='oppm_dev_password')
cur = conn.cursor()

with open('db_data_check.txt', 'w') as f:
    # Check data in existing OPPM tables
    for tbl in ['project_phases', 'oppm_deliverables', 'oppm_forecasts', 'oppm_risks', 'oppm_sub_objectives', 'oppm_objectives']:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        count = cur.fetchone()[0]
        f.write(f'{tbl}: {count} rows\n')

    # Check project_phases columns
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'project_phases' ORDER BY ordinal_position")
    f.write('\nproject_phases columns:\n')
    for r in cur.fetchall():
        f.write(f'  {r[0]}\n')

    # Check oppm_deliverables columns
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'oppm_deliverables' ORDER BY ordinal_position")
    f.write('\noppm_deliverables columns:\n')
    for r in cur.fetchall():
        f.write(f'  {r[0]}\n')

conn.close()
print("Done")
