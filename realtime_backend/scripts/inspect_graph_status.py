"""
Inspect the production memory graph status.
Prints counts of nodes, edges, and source references.
"""

import sqlite3
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))

def main():
    print("--- Collective MindGraph Production Graph Status ---")
    
    db_path = os.getenv("CMG_RT_DATA_DIR", "realtime_backend_data") + "/collective_mindgraph.sqlite3"
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return

    print(f"Database Path: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # Node counts
        print("\nNodes by Type:")
        rows = conn.execute("SELECT type, COUNT(*) as count FROM v2_graph_nodes GROUP BY type").fetchall()
        for row in rows:
            print(f"  {row['type']}: {row['count']}")
        
        # Edge counts
        print("\nEdges by Type:")
        rows = conn.execute("SELECT edge_type, COUNT(*) as count FROM v2_graph_edges GROUP BY edge_type").fetchall()
        for row in rows:
            print(f"  {row['edge_type']}: {row['count']}")
            
        # Source references
        row = conn.execute("SELECT COUNT(*) FROM v2_source_references").fetchone()
        print(f"\nSource References: {row[0]}")
        
        # Vectors
        row = conn.execute("SELECT COUNT(*) FROM v2_embeddings").fetchone()
        print(f"Vectors in Index: {row[0]}")

        # Example path
        print("\nExample Knowledge Graph Traversal (Latest Session):")
        session_row = conn.execute("SELECT id, title FROM v2_graph_nodes WHERE type = 'SESSION' ORDER BY created_at DESC LIMIT 1").fetchone()
        if session_row:
            s_id = session_row['id']
            print(f"  [SESSION] {session_row['title']} ({s_id})")
            
            # Find segments
            seg_rows = conn.execute(
                "SELECT n.id, n.text_content FROM v2_graph_nodes n JOIN v2_graph_edges e ON e.target_node_id = n.id WHERE e.source_node_id = ? AND e.edge_type = 'SESSION_HAS_SEGMENT' LIMIT 3",
                (s_id,)
            ).fetchall()
            for s_row in seg_rows:
                print(f"    └── [HAS_SEGMENT] -> {s_row['text_content'][:50]}...")
                
                # Find insights from this segment
                insight_rows = conn.execute(
                    "SELECT n.type, n.title, e.edge_type FROM v2_graph_nodes n JOIN v2_graph_edges e ON e.target_node_id = n.id WHERE e.source_node_id = ? LIMIT 2",
                    (s_row['id'],)
                ).fetchall()
                for i_row in insight_rows:
                    print(f"          └── [{i_row['edge_type']}] -> {i_row['type']}: {i_row['title']}")
        else:
            print("  No sessions found in graph.")

    except sqlite3.Error as e:
        print(f"❌ SQL Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
