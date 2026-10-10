from sqlalchemy import MetaData
from sqlalchemy.orm import Session


def delete_all_data(session: Session, commit: bool = True):
    meta = MetaData()
    meta.reflect(bind=session.get_bind())
    for table in reversed(meta.sorted_tables):
        session.execute(table.delete())
    if commit:
        session.commit()
