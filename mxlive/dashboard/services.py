import calendar
from datetime import datetime, date, time, timedelta
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


def get_user_beamtime_calendar(user, reference_date=None, num_months=3, beamtimes=None):
    """
    Generate a multi-month calendar data structure (default 3 months) for the specified user,
    annotating days with scheduled beamtime information, Access Mode colors, and shift details.

    :param user: User object
    :param reference_date: Starting reference date (defaults to today's local date)
    :param num_months: Number of sequential months to include (default 3)
    :param beamtimes: Optional pre-fetched or mocked beamtimes list/queryset
    :return: List of month dictionaries containing weeks and days
    """
    if reference_date is None:
        reference_date = timezone.localtime().date()
    elif isinstance(reference_date, datetime):
        reference_date = timezone.localtime(reference_date).date()

    today = timezone.localtime().date()
    now = timezone.now()
    tz = timezone.get_current_timezone()

    # Calculate month and year sequences
    month_seq = []
    for i in range(num_months):
        m = (reference_date.month - 1 + i) % 12 + 1
        y = reference_date.year + (reference_date.month - 1 + i) // 12
        month_seq.append((y, m))

    # Determine total window date range
    first_y, first_m = month_seq[0]
    last_y, last_m = month_seq[-1]
    _, last_days_in_last_m = calendar.monthrange(last_y, last_m)

    window_start_date = date(first_y, first_m, 1)
    window_end_date = date(last_y, last_m, last_days_in_last_m)

    window_start = timezone.make_aware(datetime.combine(window_start_date, time.min), tz)
    window_end = timezone.make_aware(datetime.combine(window_end_date, time.max), tz)

    # Fetch user's non-cancelled beamtimes intersecting the window if not provided
    if beamtimes is None and user and getattr(user, 'pk', None) and lims_cfg.USE_SCHEDULE:
        try:
            from basiclive.core.schedule.models import Beamtime
            beamtimes = list(
                user.beamtime.filter(
                    end__gte=window_start,
                    start__lte=window_end,
                    cancelled=False
                ).with_duration().select_related('beamline', 'access', 'project').order_by('start')
            )
        except Exception:
            beamtimes = []
    elif beamtimes is None:
        beamtimes = []

    # Map beamtimes with helper details
    processed_beamtimes = []
    for bt in beamtimes:
        if isinstance(bt, str):
            continue

        bt_start = getattr(bt, 'start', None)
        bt_end = getattr(bt, 'end', None)
        bt_duration = getattr(bt, 'duration', None)

        if bt_start is not None and not isinstance(bt_start, datetime):
            bt_start = now
        if bt_end is not None and not isinstance(bt_end, datetime):
            bt_end = now + timedelta(hours=8)

        if bt_start and not bt_end and bt_duration:
            bt_end = bt_start + bt_duration
        elif bt_start and not bt_end:
            bt_end = bt_start + timedelta(hours=8)
        elif not bt_start:
            bt_start = now
            bt_end = now + timedelta(hours=8)

        access = getattr(bt, 'access', None)
        access_name = getattr(access, 'name', '') if access else ''
        if not isinstance(access_name, str):
            access_name = str(access_name) if access_name else ''
        access_color = getattr(access, 'color', '#6c757d') if access else '#6c757d'
        if not isinstance(access_color, str):
            access_color = '#6c757d'

        beamline = getattr(bt, 'beamline', None)
        acronym = getattr(beamline, 'acronym', '') if beamline else ''
        if not isinstance(acronym, str):
            acronym = str(acronym) if acronym else ''

        shifts = getattr(bt, 'shifts', None)
        if shifts is None or not isinstance(shifts, (int, float)):
            try:
                shifts = int((bt_end - bt_start).total_seconds() // (8 * 3600)) or 1
            except Exception:
                shifts = 1

        is_current = (bt_start <= now <= bt_end)
        is_past = (bt_end < now)

        start_display = bt_start.strftime('%b %d, %Y')
        if hasattr(bt, 'start_date_display') and callable(bt.start_date_display):
            try:
                start_display = bt.start_date_display()
            except Exception:
                pass

        time_display = bt_start.strftime('%H:%M')
        if hasattr(bt, 'start_time_display') and callable(bt.start_time_display):
            try:
                time_display = bt.start_time_display()
            except Exception:
                pass

        processed_beamtimes.append({
            'object': bt,
            'pk': getattr(bt, 'pk', None),
            'beamline': acronym,
            'access_name': access_name,
            'access_color': access_color,
            'start': bt_start,
            'end': bt_end,
            'shifts': shifts,
            'is_current': is_current,
            'is_past': is_past,
            'start_display': start_display,
            'time_display': time_display,
            'comments': getattr(bt, 'comments', ''),
        })

    # Build calendar grids using Python's standard calendar module
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    weekday_headers = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
    months_data = []

    for y, m in month_seq:
        month_weeks = []
        month_has_beamtime = False

        for week in cal.monthdatescalendar(y, m):
            week_days = []
            for d in week:
                in_month = (d.month == m)
                is_day_today = (d == today)
                is_day_past = (d < today)

                # Find beamtimes that intersect with this day
                day_start = timezone.make_aware(datetime.combine(d, time.min), tz)
                day_end = timezone.make_aware(datetime.combine(d, time.max), tz)

                day_beamtimes = [
                    bt for bt in processed_beamtimes
                    if bt['start'] < day_end and bt['end'] > day_start
                ]

                if day_beamtimes and in_month:
                    month_has_beamtime = True

                primary_color = day_beamtimes[0]['access_color'] if day_beamtimes else None

                week_days.append({
                    'date': d,
                    'day': d.day,
                    'in_month': in_month,
                    'is_today': is_day_today,
                    'is_past': is_day_past,
                    'beamtimes': day_beamtimes,
                    'has_beamtime': bool(day_beamtimes),
                    'access_color': primary_color,
                })
            month_weeks.append(week_days)

        months_data.append({
            'year': y,
            'month': m,
            'month_name': calendar.month_name[m],
            'weekday_headers': weekday_headers,
            'weeks': month_weeks,
            'has_beamtimes': month_has_beamtime,
        })

    return months_data


def get_user_sessions(user, limit: int = 7):
    """
    Retrieve recent sessions for the user (last 365 days) up to limit (default 7).
    :param user: User object
    :param limit: Number of sessions to return
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

    active_access = Access.objects.filter(status__iexact=Access.Status.CONNECTED) if (use_acl and Access) else lims_models.Project.objects.none()

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


def get_user_guides():
    """
    Retrieve user guide list
    """

    return lims_models.Guide.objects.all()