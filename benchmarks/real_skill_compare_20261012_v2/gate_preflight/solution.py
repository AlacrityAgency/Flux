def solve(facts):
    a=facts['actor'];r=facts['resource']
    if not a['active'] or a['tenant']!=r['tenant']:return {'allowed':False}
    return {'allowed':a['id']==r['owner'] or a.get('role')=='admin'}
