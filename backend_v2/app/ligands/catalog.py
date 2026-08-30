LIGANDS: dict[str, dict[str, object]] = {
    "thc": {"name": "THC", "cid": 16078},
    "cbd": {"name": "CBD", "cid": 644019},
    "cbn": {"name": "CBN", "cid": 2543},
    "cbg": {"name": "CBG", "cid": 5315659},
    "thc-cooh": {"name": "THC-COOH", "cid": 107885},
    "11-oh-thc": {"name": "11-OH-THC", "cid": 644094},
}


def pubchem_sdf_url(ligand_id: str) -> str:
    item = LIGANDS.get(ligand_id.lower())
    if item is None:
        raise ValueError("ligand_not_found")
    return f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{item['cid']}/SDF"
