from typing import List, Dict, Any, Optional


def extract_digital_replicas(dt_data: Dict[str, Any], dr_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Estrae le digital replicas da un Digital Twin, opzionalmente filtrando per tipo.
    
    Args:
        dt_data (Dict[str, Any]): I dati del Digital Twin
        dr_type (Optional[str]): Il tipo di Digital Replica da filtrare (opzionale)
        
    Returns:
        List[Dict[str, Any]]: Lista di Digital Replicas trovate
    """
    replicas = dt_data.get("digital_replicas", [])
    
    if dr_type:
        return [dr for dr in replicas if dr.get("type") == dr_type]
    
    return replicas