from datetime import timedelta
from django.db.models import Q, Count, Max, Case, When, Value, BooleanField
from django.utils import timezone

from basiclive.core.lims.conf import settings as lims_cfg
from basiclive.core.lims import models as lims_models


def get_user_shipments(user):
    """
    Retrieve shipments belonging to the specified user:
    - Draft, Sent, or On-site shipments
    - Returned shipments within the last 365 days
    Annotated with sample, report, dataset, group, and container counts.
    """
    if not user or not getattr(user, 'pk', None):
        return []
    now = timezone.now()
    one_year_ago = now - timedelta(days=365)
    return user.shipments.filter(
        Q(status__lt=lims_models.Shipment.STATES.RETURNED)
        | Q(status=lims_models.Shipment.STATES.RETURNED, date_returned__gt=one_year_ago)
    ).annotate(
        data_count=Count('containers__samples__datasets', distinct=True),
        report_count=Count('containers__samples__datasets__reports', distinct=True),
        sample_count=Count('containers__samples', distinct=True),
        group_count=Count('groups', distinct=True),
        container_count=Count('containers', distinct=True),
    ).order_by('status', '-date_shipped', '-created').prefetch_related('project')


def get_user_beamtimes(user):
    """
    Retrieve upcoming and current beamtimes for the user if scheduling is enabled.
    """
    if not user or not getattr(user, 'pk', None):
        return []
    if not lims_cfg.USE_SCHEDULE:
        return []

    try:
        from basiclive.core.schedule.models import Beamtime
    except ImportError:
        return []

    now = timezone.now()
    return user.beamtime.filter(
        end__gte=now,
        cancelled=False
    ).with_duration().annotate(
        current=Case(
            When(start__lte=now, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        )
    ).order_by('-current', 'start')


def get_user_sessions(user, limit=7):
    """
    Retrieve recent sessions for the user (last 365 days) up to limit (default 7).
    """
    if not user or not getattr(user, 'pk', None):
        return []
    now = timezone.now()
    one_year_ago = now - timedelta(days=365)
    return user.sessions.filter(
        created__gt=one_year_ago
    ).annotate(
        data_count=Count('datasets', distinct=True),
        report_count=Count('datasets__reports', distinct=True),
        last_record=Max('datasets__end_time'),
        end=Max('stretches__end')
    ).order_by('-end', 'last_record', '-created').with_duration().prefetch_related('project', 'beamline')[:limit]


def get_staff_shipments():
    """
    Retrieve active shipments across all users (Sent or On-site).
    """
    return lims_models.Shipment.objects.filter(
        status__in=(lims_models.Shipment.STATES.SENT, lims_models.Shipment.STATES.ON_SITE)
    ).annotate(
        data_count=Count('containers__samples__datasets', distinct=True),
        report_count=Count('containers__samples__datasets__reports', distinct=True),
        sample_count=Count('containers__samples', distinct=True),
        group_count=Count('groups', distinct=True),
        container_count=Count('containers', distinct=True),
    ).order_by('status', 'project__kind__name', 'project__username', '-date_shipped').prefetch_related('project')


def get_staff_adaptors():
    """
    Retrieve adaptor containers owned by staff (superuser accounts).
    """
    return lims_models.Container.objects.filter(
        project__is_superuser=True,
        kind__locations__accepts__isnull=False,
        beamlines__isnull=True,
        status__gt=lims_models.Container.STATES.DRAFT
    ).distinct().order_by('name').select_related('parent')


def get_staff_beamlines():
    """
    Retrieve all beamlines ordered by name.
    """
    return lims_models.Beamline.objects.all().order_by('name')


def get_staff_active_connections():
    """
    Aggregate currently scheduled users, active sessions, and active remote connections.
    """
    use_acl = lims_cfg.USE_ACL
    use_schedule = lims_cfg.USE_SCHEDULE

    try:
        from basiclive.core.acl.models import Access, AccessList
    except ImportError:
        use_acl = False
        Access = AccessList = None

    try:
        from basiclive.core.schedule.models import Beamtime
    except ImportError:
        use_schedule = False
        Beamtime = None

    now = timezone.now()
    active_sessions = lims_models.Session.objects.filter(
        stretches__end__isnull=True
    ).annotate(
        data_count=Count('datasets', distinct=True),
        report_count=Count('datasets__reports', distinct=True)
    ).with_duration()

    active_access = Access.objects.filter(status__iexact=Access.STATES.CONNECTED) if (use_acl and Access) else lims_models.Project.objects.none()

    access_info = []
    connections = Access.objects.none() if (use_acl and Access) else lims_models.Project.objects.none()
    sessions = lims_models.Session.objects.none()

    # 1. Scheduled beamtimes
    if use_schedule and Beamtime:
        for bt in Beamtime.objects.filter(start__lte=now, end__gte=now).with_duration():
            bt_sessions = lims_models.Session.objects.filter(
                project=bt.project, beamline=bt.beamline
            ).filter(
                Q(stretches__end__isnull=True) | Q(stretches__end__gte=bt.start)
            ).distinct()
            sessions |= bt_sessions

            if use_acl and Access:
                bt_conns = active_access.filter(
                    user=bt.project,
                    userlist__pk__in=bt.beamline.access_lists.values_list('pk', flat=True)
                )
                connections |= bt_conns
            else:
                bt_conns = []

            access_info.append({
                'user': bt.project,
                'beamline': bt.beamline.acronym,
                'beamtime': bt,
                'sessions': bt_sessions,
                'connections': bt_conns
            })

    # 2. Active sessions not already counted
    for session in active_sessions.exclude(pk__in=[s.pk for s in sessions]):
        if use_acl and Access:
            ss_conns = active_access.filter(
                user=session.project,
                userlist__pk__in=session.beamline.access_lists.values_list('pk', flat=True)
            )
            connections |= ss_conns
        else:
            ss_conns = []

        access_info.append({
            'user': session.project,
            'beamline': session.beamline.acronym,
            'sessions': [session],
            'connections': ss_conns
        })

    # 3. Users remotely connected without schedule or session
    if use_acl and Access:
        for user_pk in active_access.exclude(pk__in=[c.pk for c in connections]).values_list('user', flat=True).distinct():
            user_conns = active_access.exclude(pk__in=[c.pk for c in connections]).filter(user__pk=user_pk)
            access_info.append({
                'user': lims_models.Project.objects.get(pk=user_pk),
                'beamline': '/'.join(
                    [bl for bl in user_conns.values_list('userlist__beamline__acronym', flat=True).distinct() if bl]
                ),
                'connections': user_conns
            })

    # Group connections by access list name and attach shipment count
    shipments = lims_models.Shipment.objects.filter(
        status__in=(lims_models.Shipment.STATES.SENT, lims_models.Shipment.STATES.ON_SITE)
    )
    for i, conn in enumerate(access_info):
        access_info[i]['shipments'] = shipments.filter(project=conn['user']).count()
        if use_acl and Access and hasattr(conn['connections'], 'filter'):
            access_info[i]['connections'] = {
                access.name: conn['connections'].filter(userlist=access)
                for access in AccessList.objects.filter(
                    pk__in=conn['connections'].values_list('userlist__pk', flat=True)
                ).distinct()
            }

    return access_info


def get_today_beamline_support():
    """
    Retrieve today's scheduled beamline support staff member if schedule and CRM are enabled.
    """
    if not lims_cfg.USE_SCHEDULE or not lims_cfg.USE_CRM:
        return None

    try:
        from basiclive.core.schedule.models import BeamlineSupport
        return BeamlineSupport.objects.filter(date=timezone.localtime().date()).first()
    except ImportError:
        return None
