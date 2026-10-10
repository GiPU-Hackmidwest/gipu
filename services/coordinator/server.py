"""Load local configuration before choosing the listening address."""
import os

from dotenv import load_dotenv
import uvicorn


if __name__ == '__main__':
    load_dotenv('.env',override=False)
    uvicorn.run('services.coordinator.app:app',
                host=os.getenv('POCKETGRID_HOST','127.0.0.1'),
                port=int(os.getenv('POCKETGRID_PORT','8787')),
                access_log=False)
