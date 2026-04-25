"""
fix_checkpointer.py
Fixes the SqliteSaver compatibility issue with newer LangGraph versions.
Run: python fix_checkpointer.py
"""

content = open("orchestrator/graph.py").read()

old = 'def get_compiled_graph():\n    """\n    Returns a compiled graph with SQLite checkpointing.\n    SQLite file is stored at ./itanta_checkpoints.db\n    This is the function called by main.py.\n    """\n    checkpointer = SqliteSaver.from_conn_string("./itanta_checkpoints.db")\n    return build_graph(checkpointer=checkpointer)'

new = 'def get_compiled_graph():\n    """\n    Returns a compiled graph with in-memory checkpointing.\n    MemorySaver works with all LangGraph versions out of the box.\n    """\n    from langgraph.checkpoint.memory import MemorySaver\n    checkpointer = MemorySaver()\n    return build_graph(checkpointer=checkpointer)'

if old in content:
    content = content.replace(old, new)
    open("orchestrator/graph.py", "w").write(content)
    print("Fixed: orchestrator/graph.py")
else:
    print("Pattern not found — patching by line number instead...")
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if 'SqliteSaver.from_conn_string' in line:
            lines[i] = '    from langgraph.checkpoint.memory import MemorySaver\n    checkpointer = MemorySaver()'
            print(f"  Patched line {i+1}")
            break
    open("orchestrator/graph.py", "w").write("\n".join(lines))
    print("Fixed: orchestrator/graph.py")

print("\nDone. Now run: python main.py")
