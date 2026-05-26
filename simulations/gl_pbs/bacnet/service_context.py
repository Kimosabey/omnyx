"""
service_context — BACnet service context classes.

SRP: Each context class owns the state for one in-flight BACnet service call
     and knows how to post its result back via an injected ResponsePoster.

OCP: New BACnet services can add their own context class without touching
     existing ones.

DIP: ResponsePoster is injected; no direct reference to global GL_GLOBALS.

Extracted from GLBACnetServiceContext, ObjectListContext, and
ObjectListContext_withSegmentation in bacnet_writer.py.
"""
from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.response_poster import ResponsePoster

logger = logging.getLogger(__name__)


# ── subscription registry ──────────────────────────────────────────────────────

class SubscriptionRegistry:
    """
    Replaces the module-level GL_Subscription_Contexts dict and the
    GL_Next_Subscription_Proc_ID counter in bacnet_writer.py.

    Thread-safe for single-threaded BACnet event loop usage
    (bacpypes runs callbacks in the same thread as the task loop).
    """

    def __init__(self) -> None:
        self._contexts: dict = {}
        self._next_id: int = 1

    def register(self, context: 'ServiceContext') -> int:
        """Assign a unique process-ID to *context* and store it."""
        proc_id = self._next_id
        self._next_id += 1
        self._contexts[proc_id] = context
        return proc_id

    def lookup(self, proc_id: int) -> Optional['ServiceContext']:
        """Return the context for *proc_id*, or None."""
        return self._contexts.get(proc_id)

    def remove(self, proc_id: int) -> None:
        self._contexts.pop(proc_id, None)


# ── general service context ────────────────────────────────────────────────────

class ServiceContext:
    """
    Holds the state for one in-flight BACnet service request (read, write,
    subscribe, readrange, timesync).

    Port of GLBACnetServiceContext.  The response_poster and subscription
    registry are injected so there are no module-level globals.
    """

    def __init__(
        self,
        address=None,
        obj_id=None,
        confirmed: Optional[bool] = None,
        lifetime: Optional[int] = None,
        http_request: Optional[dict] = None,
        response_poster: Optional['ResponsePoster'] = None,
        subscription_registry: Optional[SubscriptionRegistry] = None,
    ) -> None:
        self.address = address
        self.monitoredObjectIdentifier = obj_id
        self.issueConfirmedNotifications = confirmed
        self.lifetime = lifetime
        self.http_request = http_request
        self._response_poster = response_poster

        # Register with the subscription registry (CoV subscriptions)
        self.subscriberProcessIdentifier: Optional[int] = None
        if subscription_registry is not None:
            self.subscriberProcessIdentifier = subscription_registry.register(self)

    # ── CoV notification ──────────────────────────────────────────────────────

    def cov_notification(self, apdu) -> None:
        """
        Handle an inbound COVNotification APDU for this subscription.
        Port of GLBACnetServiceContext.cov_notification().
        """
        logger.info(
            'cov_notification — request: %s uuid: %s apdu: %s',
            self.http_request,
            self.http_request.get('request_uuid') if self.http_request else '?',
            apdu.dict_contents(),
        )
        cov_dict = self._build_cov_dict(apdu)
        self.post_response(cov_dict)

    def _build_cov_dict(self, apdu) -> dict:
        """Port of GLBACnetServiceContext.getCoVResponseDict()."""
        result: dict = {}
        try:
            result['objectId'] = apdu.monitoredObjectIdentifier
            result['changeOfValue'] = [
                {el.propertyIdentifier: str(el.value.tagList[0].app_to_object().value)}
                for el in apdu.listOfValues
            ]
            logger.info('cov_dict: %s', result)
        except Exception as exc:
            logger.error('_build_cov_dict error: %s', exc)
        return result

    # ── response posting ──────────────────────────────────────────────────────

    def post_response(self, response: dict, donotpost: bool = False) -> None:
        """
        Wrap *response* in a {request, response} envelope and post it.
        Port of GLBACnetServiceContext.post_response().
        """
        body = {'request': self.http_request, 'response': response}
        logger.info('ServiceContext.post_response — body: %s', body)
        if self._response_poster is not None:
            self._response_poster.post(body, donotpost)

    def completed(self, had_error=None) -> None:
        if had_error:
            logger.error('ServiceContext.completed — error: %r', had_error)


# ── object-list context (segmented / full read) ────────────────────────────────

class ObjectListContext:
    """
    Holds state for a discoverObjects service call on a device that supports
    segmentation (reads the whole objectList in one request).

    Also handles devices without segmentation by reading the list length
    first, then individual entries.

    Port of ObjectListContext and ObjectListContext_withSegmentation.
    The two original classes had identical completed() methods, so they are
    unified here with a segmentation_supported flag.
    """

    def __init__(
        self,
        device_id,
        device_addr,
        http_request: Optional[dict] = None,
        segmentation_supported: bool = True,
        response_poster: Optional['ResponsePoster'] = None,
    ) -> None:
        self.device_id = device_id
        self.device_addr = device_addr
        self.http_request = http_request
        self.segmentation_supported = segmentation_supported
        self._response_poster = response_poster

        # Populated by the discovery callbacks
        self.object_list: list = []
        self.object_names: list = []
        self.object_list_length: int = 0       # used for no-segmentation mode
        self._object_list_queue: Optional[deque] = None

    def completed(self, had_error=None) -> None:
        """
        Build the response payload and post it.
        Port of ObjectListContext.completed() / ObjectListContext_withSegmentation.completed().
        """
        mylist = []
        try:
            if had_error:
                logger.error('ObjectListContext.completed — error: %r', had_error)
                mylist.append(str(had_error))
            else:
                for obj_id, obj_name in zip(self.object_list, self.object_names):
                    entry = {'objectId': obj_id, 'objectName': obj_name}
                    mylist.append(entry)
                    logger.info('%s: %s', obj_id, obj_name)

            logger.info('objectList: %s', mylist)
            body = {'request': self.http_request, 'response': mylist}
            if self._response_poster is not None:
                self._response_poster.post(body)

        except Exception as exc:
            logger.error('ObjectListContext.completed error: %s', exc)
        finally:
            logger.info('discoverobjects response posted — %d objects', len(mylist))
