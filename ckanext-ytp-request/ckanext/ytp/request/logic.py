import logging

from datetime import datetime
import ckan.plugins.toolkit as tk

from ckan.lib import i18n
from sqlalchemy.sql.expression import or_

from ckan import model, authz
from ckan.common import _, c
from ckan.lib import helpers
from ckan.lib.dictization import model_dictize
from ckan.lib.helpers import url_for
from ckan.lib.mailer import MailerException
from ckan.logic import NotFound, ValidationError, check_access
from ckanext.ytp.request.model import MemberExtra
from ckanext.ytp.request.tools import get_organization_admins, get_ckan_admins

log = logging.getLogger(__name__)

try:
    import ckanext.hdx_users.helpers.mailer as hdx_mailer
except ImportError as ex:
    hdx_mailer = None
    log.warning('HDX: This is temporary for python3 migration. To be changed when hdx_users extension is migrated. '
                'This is used for tests.')




new_authz = authz
config = tk.config
# _SUBJECT_MEMBERSHIP_REQUEST = lambda: _("New membership request (%(organization)s)")
# _MESSAGE_MEMBERSHIP_REQUEST = lambda: _("""\
# User %(user)s (%(email)s) has requested membership to organization %(organization)s.
#
# %(link)s
#
# Best regards
#
# Avoindata.fi support
# valtori@avoindata.fi
# """)

# _SUBJECT_MEMBERSHIP_APPROVED = lambda: _("Organization membership approved (%(organization)s)")
# _MESSAGE_MEMBERSHIP_APPROVED = lambda: _("""\
# Your membership request to organization %(organization)s with %(role)s access has been approved.
#
# Best regards
#
# Avoindata.fi support
# valtori@avoindata.fi
# """)




def _get_default_locale():
    return config.get('ckan.locale_default', 'en')


def _get_safe_locale():
    try:
        return helpers.lang()
    except:
        return _get_default_locale()


def _reset_lang():
    try:
        i18n.set_lang(None)
    except TypeError:
        pass


def _mail_new_membership_request(locale, admin, group, url, user_obj, data_dict=None, admin_list=None):
    try:
        if admin_list:
            subject = user_obj.display_name + u' has asked to join your organisation'
            email_data = {
                'org_name': group.display_name,
                'org_membership_url': config.get('ckan.site_url') + '/organization/members/' + group.name,
                'user_fullname': user_obj.display_name,
                'user_email': user_obj.email,
                'message': data_dict.get('message')
            }
            hdx_mailer.mail_recipient(admin_list, subject, email_data, footer=user_obj.email,
                                      snippet='email/content/join_organization_request.html')

            subject = u'Your request to join organisation ' + group.display_name
            email_data = {
                'org_name': group.display_name,
                'user_fullname': user_obj.display_name,
                'user_email': user_obj.email
            }
            hdx_mailer.mail_recipient([{'display_name': user_obj.display_name, 'email': user_obj.email}],
                                      subject, email_data,footer=user_obj.email,
                                      snippet='email/content/join_organization_request_confirmation_to_user.html')

    except MailerException as e:
        log.error(e)
    # finally:
    #     set_lang(current_locale)


def _mail_process_status(locale, member_user, approve, group_name, capacity, group_id=None):
    try:
        if approve:
            subject = u'Approval of your request to join organisation ' + group_name
            email_data = {
                'user_fullname': member_user.display_name,
                'org_name': group_name,
                'capacity': capacity
            }
            hdx_mailer.mail_recipient([{'display_name': member_user.display_name, 'email': member_user.email}], subject,
                                      email_data, footer=member_user.email,
                                      snippet='email/content/join_organization_approval_to_user.html')
            admin_list = []
            if group_id:
                for admin in get_organization_admins(group_id):
                    if admin.email != member_user.email:
                        admin_list.append({'display_name': admin.display_name, 'email': admin.email})
                subject = u'Join request approved for organisation ' + group_name
                email_data = {
                    'user_fullname': member_user.display_name,
                    'user_email': member_user.email,
                    'org_name': group_name,
                }
                hdx_mailer.mail_recipient(admin_list, subject, email_data, footer=member_user.email,
                                          snippet='email/content/join_organization_approval_to_admins.html')

        else:
            subject = u'Denial of your request to join organisation ' + group_name
            email_data = {
                'user_fullname': member_user.display_name,
                'org_name': group_name,
            }
            hdx_mailer.mail_recipient([{'display_name': member_user.display_name, 'email': member_user.email}], subject,
                                      email_data, footer=member_user.email,
                                      snippet='email/content/join_organization_reject_to_user.html')
            admin_list = []
            if group_id:
                for admin in get_organization_admins(group_id):
                    admin_list.append({'display_name': admin.display_name, 'email': admin.email})
                subject = u'Join request denied for organisation ' + group_name
                email_data = {
                    'user_fullname': member_user.display_name,
                    'user_email': member_user.email,
                    'org_name': group_name,
                }
                hdx_mailer.mail_recipient(admin_list, subject, email_data, footer=member_user.email,
                                          snippet='email/content/join_organization_reject_to_admins.html')

    except MailerException as e:
        log.error(e)



def _member_list_dictize(obj_list, context, sort_key=lambda x: x['group_id'], reverse=False):
    """ Helper to convert member list to dictionary """
    result_list = []
    for obj in obj_list:
        if obj.group:
            member_dict = model_dictize.member_dictize(obj, context)
            member_dict['group_name'] = obj.group.name
            user = model.Session.query(model.User).get(obj.table_id)
            member_dict['user_name'] = user.name
            result_list.append(member_dict)
    return sorted(result_list, key=sort_key, reverse=reverse)


def _create_member_request(context, data_dict):
    """ Helper to create member request """
    changed = False
    role = data_dict['role']
    group = model.Group.get(data_dict['group'])

    if not group or group.type != 'organization':
        raise NotFound

    user = context['user']

    if new_authz.is_sysadmin(user):
        raise ValidationError({}, {_("Role"): _("As a sysadmin, you already have access to all organizations")})

    userobj = model.User.get(user)

    member = model.Session.query(model.Member).filter(model.Member.table_name == "user").filter(
        model.Member.table_id == userobj.id) \
        .filter(model.Member.group_id == group.id).filter(
        or_(model.Member.state == 'active', model.Member.state == 'pending')).first()

    if member:
        if member.state == 'pending':
            message = _("You already have a pending request to the organization")
        else:
            message = _("You are already part of the organization")

        raise ValidationError({"organization": _("Duplicate organization request")}, {_("Organization"): message})

    member = model.Session.query(model.Member).filter(model.Member.table_name == "user").filter(
        model.Member.table_id == userobj.id) \
        .filter(model.Member.group_id == group.id).first()

    if not member:
        member = model.Member(table_name="user", table_id=userobj.id,
                              group=group, group_id=group.id, capacity=role, state='pending')
        changed = True

    locale = _get_safe_locale()

    if member.state != 'pending' or changed:
        member.state = 'pending'
        member.capacity = role

        if changed:
            model.Session.add(member)

        model.Session.flush()

        extra = MemberExtra(member_id=member.id, key="created", value=datetime.utcnow().isoformat())
        extra.save()

        model.repo.commit()
        changed = True

    url = config.get('ckan.site_url', "")
    if url:
        url = url + url_for('ytp_request.show', member_id=member.id)

    admin_list = []
    if role == 'admin':
        for admin in get_ckan_admins():
            admin_list.append({'display_name': admin.display_name, 'email': admin.email})
            # _mail_new_membership_request(locale, admin, group, url, userobj, data_dict)
    else:
        for admin in get_organization_admins(group.id):
            admin_list.append({'display_name': admin.display_name, 'email': admin.email})
            # _mail_new_membership_request(locale, admin, group, url, userobj, data_dict)
    _mail_new_membership_request(locale, None, group, url, userobj, data_dict, admin_list)
    return member, changed


def member_request_create(context, data_dict):
    ''' Create new member request. User is taken from context.

    :param group: name of the group or organization
    :type group: string
    '''
    check_access('member_request_create', context, data_dict)
    member, _changed = _create_member_request(context, data_dict)
    return model_dictize.member_dictize(member, context)


def member_request_show(context, data_dict):
    ''' Create new member request. User is taken from context.

    :param member: id of the member object
    :type member: string

    :param fetch_user: fetch related user data
    :type fetch_user: boolean
    '''
    check_access('member_request_show', context, data_dict)

    model = context['model']
    member_id = data_dict.get("member")
    fetch_user = data_dict.get("fetch_user", False)
    member = model.Session.query(model.Member).get(member_id)

    if not member.group.is_organization:
        raise NotFound

    data = model_dictize.member_dictize(member, context)

    if fetch_user:
        member_user = model.Session.query(model.User).get(member.table_id)
        data['user'] = model_dictize.user_dictize(member_user, context)

    return data


def member_request_list(context, data_dict):
    ''' List my member requests.

    :param group: name of the group (optional)
    :type group: string
    '''
    check_access('member_request_list', context, data_dict)

    user = context['user']
    user_object = model.User.get(user)
    sysadmin = new_authz.is_sysadmin(user)

    query = model.Session.query(model.Member).filter(model.Member.table_name == "user").filter(
        model.Member.state == 'pending')

    if not sysadmin:
        admin_in_groups = model.Session.query(model.Member).filter(model.Member.state == "active").filter(
            model.Member.table_name == "user") \
            .filter(model.Member.capacity == 'admin').filter(model.Member.table_id == user_object.id)

        if admin_in_groups.count() <= 0:
            return []

        query = query.filter(model.Member.group_id.in_(admin_in_groups.values(model.Member.group_id)))

    group = data_dict.get('group', None)
    if group:
        group_object = model.Group.get(group)
        if group_object:
            query = query.filter(model.Member.group_id == group_object.id)

    members = query.all()

    return _member_list_dictize(members, context)


def _process_request(context, member, action, new_role=None):
    user = context["user"]

    approve = action == 'approve'  # else 'reject' or 'cancel'

    state = "active" if approve else "deleted"

    if not member or not member.group.is_organization:
        raise NotFound

    member.state = state
    if new_role:
        member.capacity = new_role

    for extra in member.extras:
        if extra.key == 'created':
            extra.delete()

    member.save()
    model.repo.commit()

    member_user = model.Session.query(model.User).get(member.table_id)
    admin_user = model.User.get(user)

    # locale = member.extras.get('locale', None) or _get_default_locale()
    locale = _get_default_locale()
    _log_process(member_user, member.group.display_name, approve, admin_user)
    _mail_process_status(locale, member_user, approve, member.group.display_name, member.capacity, member.group_id)

    return model_dictize.member_dictize(member, context)


def _log_process(member_user, member_org, approve, admin_user):
    if approve:
        log.info("Membership request of %s approved to %s by admin: %s" %
                 (member_user.fullname if member_user.fullname else member_user.name, member_org,
                  admin_user.fullname if admin_user.fullname else admin_user.name))
    else:
        log.info("Membership request of %s rejected to %s by admin: %s" %
                 (member_user.fullname if member_user.fullname else member_user.name, member_org,
                  admin_user.fullname if admin_user.fullname else admin_user.name))


def member_request_membership_cancel(context, data_dict):
    ''' Cancel organization membership (not request). Member or organization_id must be provided.

    :param organization_id: id of the organization
    :type member: string
    '''
    check_access('member_request_membership_cancel', context, data_dict)

    organization_id = data_dict.get("organization_id")
    query = model.Session.query(model.Member).filter(model.Member.state == 'active') \
        .filter(model.Member.table_name == 'user').filter(model.Member.table_id == c.userobj.id).filter(
        model.Member.group_id == organization_id)
    member = query.first()

    if not member:
        raise NotFound

    return _process_request(context, member, 'cancel')


def member_request_cancel(context, data_dict):
    ''' Cancel own request. Member or organization_id must be provided.

    :param member: id of the member
    :type member: string

    :param organization_id: id of the organization
    :type member: string
    '''
    check_access('member_request_cancel', context, data_dict)

    member_id = data_dict.get("member", None)
    member = None
    if member_id:
        member = model.Session.query(model.Member).get(data_dict.get("member"))
    else:
        organization_id = data_dict.get("organization_id")
        query = model.Session.query(model.Member).filter(
            or_(model.Member.state == 'pending', model.Member.state == 'active')) \
            .filter(model.Member.table_name == 'user').filter(model.Member.table_id == c.userobj.id).filter(
            model.Member.group_id == organization_id)
        member = query.first()

    if not member:
        raise NotFound

    return _process_request(context, member, 'cancel')


def member_request_process(context, data_dict):
    ''' Approve or reject member request.

    :param member: id of the member
    :type member: string

    :param role: role decided by the org admin (optional)
    :type role: string

    :param approve: approve or reject request
    :type approve: boolean
    '''
    check_access('member_request_process', context, data_dict)
    member = model.Session.query(model.Member).get(data_dict.get("member"))
    return _process_request(context, member, 'approve' if data_dict.get('approve') else 'reject', data_dict.get('role'))
