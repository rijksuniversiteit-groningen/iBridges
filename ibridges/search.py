"""Data query."""
from __future__ import annotations

from typing import Optional, Union

from ibridges import keywords as kw
from ibridges.path import IrodsPath
from ibridges.session import Session


def search_data(session: Session, path: Optional[Union[str, IrodsPath]] = None,
           checksum: Optional[str] = None, key_vals: Optional[dict] = None) -> list[dict]:
    """Retrieve all collections and data objects.

    (the absolute collection path,
    data object or collection name) to the given user-defined and system metadata.
    By Default all accessible collections and data objects will be returned.
    Wildcard: %

    Parameters
    ----------
    session:
        Session to search with.
    path: str
        (Partial) path or IrodsPath
    checksum: str
        (Partial) checksum
    key_vals : dict
        Attribute name mapping to values.

    Returns
    -------
    list: [dict]
        List of dictionaries with keys:
        COLL_NAME (absolute path of the collection),
        DATA_NAME (name of the data object),
        D_DATA_CHECKSUM (checksum of the data object)
        The latter two keys are only present of the found item is a data object.

    """
    if path is None and checksum is None and key_vals is None:
        raise ValueError(
                "QUERY: Error while searching in the metadata: No query criteria set." \
                        + " Please supply either a path, checksum or key_vals.")

    # create the query for collections; we only want to return the collection name
    coll_query = session.irods_session.query(kw.COLL_NAME)
    # create the query for data objects; we need the collection name, the data name and its checksum
    data_query = session.irods_session.query(kw.COLL_NAME, kw.DATA_NAME,
                                             kw.DATA_CHECKSUM)
    if path:
        coll_query = coll_query.filter(kw.LIKE(kw.COLL_NAME, str(path)))
        data_query = data_query.filter(kw.LIKE(kw.COLL_NAME, str(path)))
    if key_vals:
        for key in key_vals:
            data_query.filter(kw.LIKE(kw.META_DATA_ATTR_NAME, key))
            coll_query.filter(kw.LIKE(kw.META_COLL_ATTR_NAME, key))
            if key_vals[key]:
                data_query.filter(kw.LIKE(kw.META_DATA_ATTR_VALUE, key_vals[key]))
                coll_query.filter(kw.LIKE(kw.META_COLL_ATTR_VALUE, key_vals[key]))
    if checksum:
        data_query = data_query.filter(kw.LIKE(kw.DATA_CHECKSUM, checksum))
    # gather results
    results = list(data_query.get_results())
    if checksum is None:
        coll_res = list(coll_query.get_results())
        if len(coll_res) > 0:
            results.extend(coll_res)

    for item in results:
        if isinstance(item, dict):
            new_keys = [k.icat_key for k in item.keys()]
            for n_key, o_key in zip(new_keys, item.keys()):
                item[n_key] = item.pop(o_key)

    return results
