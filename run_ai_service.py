#!/usr/bin/env python
"""Start AI service with proper path setup."""
import sys
import os

# Add shared module to path
workspace_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(workspace_root, "shared"))
sys.path.insert(0, os.path.join(workspace_root, "services", "ai"))

# Import and run
if __name__ == "__main__":
    from main import app
    import uvicorn
    
    print(f"Starting AI service on http://0.0.0.0:8001")
    print(f"GraphQL endpoint: http://localhost:8001/api/v1/workspaces/{{workspace_id}}/graphql")
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
