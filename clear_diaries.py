from pathlib import Path
from app.utils.db_utils import get_connection

# Define the database path
db_path = Path("storage/db/app.db")

# Ensure the parent directory exists
db_path.parent.mkdir(parents=True, exist_ok=True)

# Connect to the database and delete all diary entries
with get_connection(str(db_path)) as conn:
    conn.execute("DELETE FROM diaries")
    conn.commit()
    print("All diary entries have been deleted successfully.")