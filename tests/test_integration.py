from backend.analysis.change_analysis_engine import analyze_impact
from ai_agent_groq import generate_insights

changed_files = ['terraform/customer_database.tf']
bfs_result = analyze_impact(changed_files)

print('BFS Result:')
print(f'  Changed Resource: {bfs_result["changed_resource"]}')
print(f'  Affected Services: {len(bfs_result["affected_services"])} services')
print(f'  Business Impact: {bfs_result["business_impact"]}%')

ai_result = generate_insights(bfs_result['affected_services'], bfs_result['business_impact'])

print('AI Result:')
print(f'  Severity: {ai_result["severity"]}')
print(f'  Simulation: {ai_result["simulation"][:150]}...')
print('✅ BFS + AI Integration WORKING!')
