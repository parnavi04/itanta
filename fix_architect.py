"""
fix_architect.py
Fixes the DataModel relationships validation error in architect_agent.py
Run: python fix_architect.py
"""

content = open("agents/architect_agent.py", encoding="utf-8").read()

old = "        data_models=[DataModel(**m) for m in data.get(\"data_models\", [])],"

new = """        data_models=[
            DataModel(**{
                **m,
                "relationships": [
                    r if isinstance(r, str)
                    else r.get("model", str(r))
                    for r in m.get("relationships", [])
                ]
            })
            for m in data.get("data_models", [])
        ],"""

if old in content:
    content = content.replace(old, new)
    open("agents/architect_agent.py", "w", encoding="utf-8").write(content)
    print("Fixed: agents/architect_agent.py")
else:
    print("Pattern not found — trying line-by-line patch...")
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "data_models=[DataModel(**m)" in line:
            lines[i] = """        data_models=[
            DataModel(**{
                **m,
                "relationships": [
                    r if isinstance(r, str)
                    else r.get("model", str(r))
                    for r in m.get("relationships", [])
                ]
            })
            for m in data.get("data_models", [])
        ],"""
            print(f"  Patched line {i+1}")
            break
    open("agents/architect_agent.py", "w", encoding="utf-8").write("\n".join(lines))
    print("Fixed: agents/architect_agent.py")

print("Done. Now run: python main.py")
