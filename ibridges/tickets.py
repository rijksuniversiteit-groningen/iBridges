"""Ticket operations."""
from __future__ import annotations

from collections import namedtuple
from datetime import date, datetime
from typing import Iterable, Optional, Union

import irods.ticket
from irods.models import TicketQuery

import ibridges.keywords as kw
from ibridges.session import Session

TicketData = namedtuple('TicketData', ["name", "type", "path", "expiration_date"])

class Tickets():
    """Irods Ticket operations."""

    def __init__(self, session: Session):
        """IRODS data operations initialization.

        Parameters
        ----------
        session : session.Session
            instance of the Session class

        """
        self.session = session
        self._all_tickets = self.update_tickets()

    def create_ticket(self, obj_path: str,
                      ticket_type: Optional[str] = 'read',
                      expiry_date: Optional[Union[str, datetime, date]] = None) -> tuple:
        """Create an iRODS ticket.

        This allows read access to the object referenced by `obj_path`.

        Parameters
        ----------
        obj_path : str
            Collection or data object path to create a ticket for.
        ticket_type: str
            read or write, default read
        expiry_date : str
            Optional expiration date in the form: strftime('%Y-%m-%d.%H:%M:%S')

        Returns
        -------
        tuple
            Name of ticket and if expiration string successfully set:
            (str, bool)

        """
        ticket = irods.ticket.Ticket(self.session.irods_session)
        ticket.issue(ticket_type, obj_path)
        expiration_set = False
        if expiry_date is not None:
            if isinstance(expiry_date, date):
                expiry_date = datetime.combine(expiry_date, datetime.min.time())
            if isinstance(expiry_date, datetime):
                expiry_date = expiry_date.strftime('%Y-%m-%d.%H:%M:%S')
            if not isinstance(expiry_date, str):
                raise ValueError("Expecting datetime, date or string type for 'expiry_date' "
                                 f"argument, got {type(expiry_date)}")
            try:
                expiration_set = ticket.modify('expire', expiry_date) == ticket
            except Exception as error:
                self.delete_ticket(ticket)
                raise ValueError('Could not set expiration date') from error
        self.update_tickets()
        return ticket.ticket, expiration_set

    def __iter__(self) -> Iterable[TicketData]:
        """Iterate over all ticket data."""
        yield from self.update_tickets()

    @property
    def all_ticket_strings(self) -> list[str]:
        """Get the names of all tickets."""
        return [tick_data.name for tick_data in self._all_tickets]

    def get_ticket(self, ticket_str: str) -> Optional[irods.ticket.Ticket]:
        """Obtain a ticket using its string identifier."""
        if ticket_str in self.all_ticket_strings:
            return irods.ticket.Ticket(self.session.irods_session, ticket=ticket_str)
        raise KeyError(f"Cannot obtain ticket: ticket with ticket_str '{ticket_str}' "
                       "does not exist.")

    def delete_ticket(self, ticket: irods.ticket.Ticket, check: bool = False):
        """Delete irods ticket."""
        if ticket.string in self.all_ticket_strings:
            ticket.delete()
            self.update_tickets()
        elif check:
            raise KeyError(f"Cannot delete ticket: ticket '{ticket}' does not exist (anymore).")

    def update_tickets(self) -> list[TicketData]:
        """Retrieve all tickets and their metadata belonging to the user.

        Parameters
        ----------
        update : bool
            Refresh information from server.

        Returns
        -------
        list
            [(ticket string, ticket type, irods obj/coll path, expiry data in epoche)]

        """
        user = self.session.username
        self._all_tickets = []
        for row in self.session.irods_session.query(TicketQuery.Ticket).filter(
                TicketQuery.Owner.name == user):
            self._all_tickets.append(
                TicketData(row[TicketQuery.Ticket.string],
                           row[TicketQuery.Ticket.type],
                           self._id_to_path(str(row[TicketQuery.Ticket.object_id])),
                           datetime.fromtimestamp(int(row[TicketQuery.Ticket.expiry_ts]))
                ))
        return self._all_tickets

    def clear(self):
        """Delete all tickets."""
        for tick_data in self.update_tickets():
            tick = self.get_ticket(tick_data.name)
            self.delete_ticket(tick)
        self.update_tickets()

    def _id_to_path(self, itemid: str) -> str:
        """Get IRODS path from a given an iRODS item id.

        The item (data object or collection) id should come from the
        TicketQuery.Ticket.object_id.

        Parameters
        ----------
        itemid : str
            iRODS identifier for a collection or data object
            (str(row[TicketQuery.Ticket.object_id]))

        Returns
        -------
        str
            collection or data object path
            returns '' if the identifier does not exist any longer

        """
        data_query = self.session.irods_session.query(kw.COLL_NAME, kw.DATA_NAME)
        data_query = data_query.filter(kw.DATA_ID == itemid)

        if len(list(data_query)) > 0:
            res = next(data_query.get_results())
            return list(res.values())[0] + "/" + list(res.values())[1]
        coll_query = self.session.irods_session.query(kw.COLL_NAME)
        coll_query = coll_query.filter(kw.COLL_ID == itemid)
        if len(list(coll_query)) > 0:
            res = next(coll_query.get_results())
            return list(res.values())[0]
        return ''
