from .blueprints_declaration import portal_bp
from flask import render_template, g, flash
from ..models.company import Company
from flask.ext.login import login_required
from ..models.portal import PortalDivisionType
from ..models.translate import TranslateTemplate
from utils.db_utils import db
from ..models.portal import MemberCompanyPortal, Portal, PortalLayout, PortalDivision, \
    PortalDivisionSettingsCompanySubportal, PortalConfig
from .request_wrapers import ok, tos_required, check_right
from ..models.articles import ArticlePortalDivision, ArticleCompany, Article
from ..models.company import UserCompany
from ..models.pr_base import PRBase, Grid
import copy
import re
from .pagination import pagination
from config import Config
from ..models.rights import PublishUnpublishInPortal, MembersRights, MembershipRights, RequireMembereeAtPortalsRight, \
    PortalManageMembersCompaniesRight, UserIsEmployee, EditPortalRight


@portal_bp.route('/<any(create,update):create_or_update>/company/<string:company_id>/', methods=['GET'])
@portal_bp.route('/<any(create,update):create_or_update>/company/<string:company_id>/portal/<string:portal_id>/',
                 methods=['GET'])
@login_required
@check_right(EditPortalRight, ['company_id'])
def profile(create_or_update, company_id, portal_id=None):
    return render_template('portal/portal_create.html', company=Company.get(company_id))


@portal_bp.route('/<any(create,update):create_or_update>/company/<string:company_id>/', methods=['POST'])
@portal_bp.route('/<any(create,update):create_or_update>/company/<string:company_id>/portal/<string:portal_id>/',
                 methods=['POST'])
@login_required
@ok
@check_right(EditPortalRight, ['company_id'])
def profile_load(json, create_or_update, company_id, portal_id=None):
    action = g.req('action', allowed=['load', 'save', 'validate'])
    layouts = [x.get_client_side_dict() for x in db(PortalLayout).all()]
    types = {x.id: x.get_client_side_dict() for x in PortalDivisionType.get_division_types()}
    company = Company.get(company_id)
    portal = Portal() if portal_id is None else Portal.get(portal_id)
    if action == 'load':
        ret = {'company': company.get_client_side_dict(),
               'layouts': layouts, 'division_types': types}
        if create_or_update == 'update':
            ret['portal'] = {}
            ret['portal_company_members'] = company.portal_members
            ret['host_profi_or_own'] = 'profi' if re.match(r'^profireader\.', ret['portal']['hostname']) else 'own'
        else:
            ret['portal_company_members'] = [company.get_client_side_dict()]
            ret['portal'] = {'company_owner_id': company_id, 'name': '', 'host': '',

                             'logo_file_id': company.logo_file_id,
                             'host_profi_or_own': 'profi',
                             'host_own': '',
                             'host_profi': '',
                             'portal_layout_id': layouts[0]['id'],
                             'divisions': [
                                 {'name': 'index page', 'portal_division_type_id': 'index',
                                  'page_size': ''},
                                 {'name': 'news', 'portal_division_type_id': 'news', 'page_size': ''},
                                 {'name': 'events', 'portal_division_type_id': 'events',
                                  'page_size': ''},
                                 {'name': 'catalog', 'portal_division_type_id': 'catalog',
                                  'page_size': ''},
                                 {'name': 'our subportal',
                                  'portal_division_type_id': 'company_subportal',
                                  'page_size': '',
                                  'settings': {'company_id': ret['portal_company_members'][0]['id']}}]}
            ret['logo'] = portal.get_logo_client_side_dict()
        return ret
    else:
        json_portal = json['portal']
        if create_or_update == 'update':
            pass
        elif create_or_update == 'create':
            page_size_for_config = dict()
            for a in json_portal['divisions']:
                page_size_for_config[a.get('name')] = a.get('page_size') \
                    if type(a.get('page_size')) is int and a.get('page_size') != 0 \
                    else Config.ITEMS_PER_PAGE
            # print(json)
            json_portal['host'] = (json_portal['host_profi'] + '.profireader.com') \
                if json_portal['host_profi_or_own'] == 'profi' else json_portal['host_own']

            portal = Portal(company_owner=company, **g.filter_json(json_portal, 'name', 'portal_layout_id', 'host'))
            divisions = []
            for division_json in json['portal']['divisions']:
                division = PortalDivision(portal, portal_division_type_id=division_json['portal_division_type_id'],
                                          position=len(json['portal']['divisions']) - len(divisions),
                                          name=division_json['name'])
                if division_json['portal_division_type_id'] == 'company_subportal':
                    division.settings = {'member_company_portal': portal.company_members[0]}
                divisions.append(division)
            # self, portal=portal, portal_division_type=portal_division_type, name='', settings={}
            portal.divisions = divisions
            PortalConfig(portal=portal, page_size_for_divisions=page_size_for_config)
        if action == 'save':
            portal.setup_created_portal(g.filter_json(json_portal, 'logo_file_id')).save()
            portal_dict = portal.set_logo_client_side_dict(json['logo']).save().get_client_side_dict()
            return portal_dict
        else:
            return portal.validate(create_or_update == 'create')


@portal_bp.route('/apply_company/<string:company_id>', methods=['POST'])
@login_required
@ok
@check_right(RequireMembereeAtPortalsRight, ['company_id'])
def apply_company(json, company_id):
    MemberCompanyPortal.apply_company_to_portal(company_id=company_id,
                                                portal_id=json['portal_id'])
    return {'portals_partners': [portal.get_client_side_dict(fields='name, company_owner_id,id')
                                 for portal in PublishUnpublishInPortal(company=company_id).get_portals_where_company_is_member()],
            'company_id': company_id}


@portal_bp.route('/profile_edit/<string:portal_id>/', methods=['GET'])
@login_required
@check_right(EditPortalRight, ['portal_id'])
def profile_edit(portal_id):
    return render_template('portal/portal_profile_edit.html', company=Portal.get(portal_id).own_company)


@portal_bp.route('/profile_edit/<string:portal_id>/', methods=['POST'])
@login_required
@check_right(EditPortalRight, ['portal_id'])
@ok
def profile_edit_load(json, portal_id):
    portal = db(Portal, id=portal_id).one()

    return {'portal': portal.get_client_side_dict('id, name, divisions, own_company, portal_bound_tags_select.*'),
            'tag': []}


@portal_bp.route('/portals_partners/<string:company_id>/', methods=['GET'])
@login_required
@check_right(UserIsEmployee, ['company_id'])
def portals_partners(company_id):
    return render_template('company/portals_partners.html',
                           company=Company.get(company_id),
                           actions={'require_memberee': RequireMembereeAtPortalsRight(company=company_id).is_allowed()})


@portal_bp.route('/portals_partners/<string:company_id>/', methods=['POST'])
@login_required
@ok
@check_right(UserIsEmployee, ['company_id'])
def portals_partners_load(json, company_id):
    subquery = Company.subquery_portal_partners(company_id, json.get('filter'),
                                                filters_exсept=MembersRights.INITIALLY_FILTERED_OUT_STATUSES)
    partners_g, pages, current_page, count = pagination(subquery, **Grid.page_options(json.get('paginationOptions')))
    partner_list = [
        PRBase.merge_dicts(partner.get_client_side_dict(fields='id,status,portal.own_company,portal,rights'),
                           {'actions': MembershipRights(company=company_id, member_company=partner).actions()},
                           {'who': MembershipRights.MEMBERSHIP})
        for partner in partners_g]
    return {'page': current_page,
            'grid_data': partner_list,
            'grid_filters': {k: [{'value': None, 'label': TranslateTemplate.getTranslate('', '__-- all --')}] + v for
                             (k, v) in {'status': [{'value': status, 'label': status} for status in
                                                   MembershipRights.STATUSES]}.items()},
            'grid_filters_except': list(MembershipRights.INITIALLY_FILTERED_OUT_STATUSES),
            'total': count}


@portal_bp.route('/portals_partners_change_status/<string:company_id>/<string:portal_id>', methods=['POST'])
@login_required
@ok
@check_right(RequireMembereeAtPortalsRight, ['company_id'])
def portals_partners_change_status(json, company_id, portal_id):
    partner = MemberCompanyPortal.get(portal_id=portal_id, company_id=json.get('partner_id'))
    employee = UserCompany.get(company_id=company_id)
    if MembershipRights(company=json.get('partner_id'), member_company=partner).action_is_allowed(json.get('action'), employee) == True:
        partner.set_client_side_dict(
                status=MembershipRights.STATUS_FOR_ACTION[json.get('action')])
        partner.save()
    return partner.get_client_side_dict()


@portal_bp.route('/<string:company_id>/company_partner_update/<string:member_id>/', methods=['GET'])
@login_required
@check_right(PortalManageMembersCompaniesRight, ['company_id', 'member_id'])
def company_partner_update(company_id, member_id):
    return render_template('company/company_partner_update.html',
                           company=Company.get(company_id),
                           member=MemberCompanyPortal.get(Company.get(company_id).own_portal.id,
                                                          company_id=member_id).company.get_client_side_dict('id, status'))


@portal_bp.route('/<string:company_id>/company_partner_update/<string:member_id>/', methods=['POST'])
@login_required
@ok
@check_right(PortalManageMembersCompaniesRight, ['company_id', 'member_id'])
def company_update_load(json, company_id, member_id):
    action = g.req('action', allowed=['load', 'validate', 'save'])
    member = MemberCompanyPortal.get(Company.get(company_id).own_portal.id, member_id)
    if action == 'load':
        return {'member': member.get_client_side_dict(more_fields='company'),
                'statuses_available': MembersRights.get_avaliable_statuses(),
                'employeer': Company.get(company_id).get_client_side_dict()}
    else:
        member.set_client_side_dict(status=json['member']['status'], rights=json['member']['rights'])
        if action == 'validate':
            member.detach()
            validate = member.validate(False)
            return validate
        else:
            member.save()
    return member.get_client_side_dict()

@portal_bp.route('/company_partners_change_status/<string:company_id>/<string:portal_id>', methods=['POST'])
@login_required
@ok
@check_right(PortalManageMembersCompaniesRight, ['company_id'])
def company_partners_change_status(json, company_id, portal_id):
    partner = MemberCompanyPortal.get(portal_id=portal_id, company_id=json.get('partner_id'))
    employee = UserCompany.get(company_id=company_id)
    print(partner.id)
    print(company_id, portal_id)
    print(MembersRights(company=json.get('partner_id'), member_company=partner).action_is_allowed(json.get('action'), employee))
    if MembersRights(company=json.get('partner_id'), member_company=partner).action_is_allowed(json.get('action'), employee) == True:
        partner.set_client_side_dict(
                status=MembersRights.STATUS_FOR_ACTION[json.get('action')])
        partner.save()
    return partner.get_client_side_dict()

@portal_bp.route('/companies_partners/<string:company_id>/', methods=['GET'])
@login_required
@check_right(UserIsEmployee, ['company_id'])
def companies_partners(company_id):
    return render_template('company/companies_partners.html', company=Company.get(company_id),
                           rights_user_in=UserCompany.get(company_id=company_id).has_rights(
                                   UserCompany.RIGHT_AT_COMPANY.PORTAL_MANAGE_MEMBERS_COMPANIES))


@portal_bp.route('/companies_partners/<string:company_id>/', methods=['POST'])
@login_required
@ok
@check_right(UserIsEmployee, ['company_id'])
def companies_partners_load(json, company_id):
    subquery = Company.subquery_company_partners(company_id, json.get('filter'),filters_exсept=MembersRights.INITIALLY_FILTERED_OUT_STATUSES)
    members, pages, current_page, count = pagination(subquery, **Grid.page_options(json.get('paginationOptions')))
    return {'grid_data': [PRBase.merge_dicts({'member': member.get_client_side_dict(more_fields='company'),
                           'company_id': company_id, 'portal_id': db(Portal, company_owner_id=company_id).first().id},
                           {'actions': MembersRights(company=company_id, member_company=member).actions()},{'who':MembersRights.MEMBER})
                          for member in members],
            'grid_filters': {k: [{'value': None, 'label': TranslateTemplate.getTranslate('', '__-- all --')}] + v for
                             (k, v) in {'member.status': [{'value': status, 'label': status} for status in MembersRights.STATUSES]}.items()},
            'grid_filters_except': list(MembersRights.INITIALLY_FILTERED_OUT_STATUSES),
            'total': count,
            'page': current_page}


@portal_bp.route('/search_for_portal_to_join/', methods=['POST'])
@ok
@login_required
def search_for_portal_to_join(json):
    if RequireMembereeAtPortalsRight(company=json['company_id']).is_allowed() != True:
        return False
    portals_partners = Portal.search_for_portal_to_join(
            json['company_id'], json['search'])
    return portals_partners


@portal_bp.route('/company/<string:company_id>/publications/', methods=['GET'])
@login_required
@check_right(UserIsEmployee, ['company_id'])
def publications(company_id):
    return render_template('portal/portal_publications.html', company=Company.get(company_id))


def get_publication_dict(publication):
    ret = publication.get_client_side_dict()
    if ret.get('long'):
        del ret['long']
    ret['actions'] = PublishUnpublishInPortal(publication=publication, division=publication.division,
                                              company=publication.division.portal.own_company).actions()

    return ret


@portal_bp.route('/company/<string:company_id>/publications/', methods=['POST'])
@login_required
@check_right(UserIsEmployee, ['company_id'])
@ok
def publications_load(json, company_id):
    company = Company.get(company_id)
    portal = company.own_portal
    subquery = ArticlePortalDivision.subquery_portal_articles(portal.id, json.get('filter'), json.get('sort'))
    publications, pages, current_page, count = pagination(subquery, **Grid.page_options(json.get('paginationOptions')))
    # grid_filters = {
    #     'publication_status':Grid.filter_for_status(ArticlePortalDivision.STATUSES),
    #     'company': [{'value': company_id, 'label': company} for company_id, company  in
    #                 ArticlePortalDivision.get_companies_which_send_article_to_portal(portal).items()]
    # }
    return {'company': company.get_client_side_dict(),
            'portal': portal.get_client_side_dict(),
            'rights_user_in_company': UserCompany.get(company_id=company_id).rights,
            'grid_data': list(map(get_publication_dict, publications)),
            'total': count}


@portal_bp.route('/company/<string:company_id>/tags/', methods=['GET'])
@login_required
# @check_right(UserIsEmployee, 'company_id')
def tags(company_id):
    return render_template('portal/tags.html', company=Company.get(company_id))


@portal_bp.route('/company/<string:company_id>/tags/', methods=['POST'])
@login_required
# @check_right(UserIsEmployee, 'company_id')
@ok
def tags_load(json, company_id):
    action = g.req('action', allowed=['load', 'save', 'validate'])
    company = Company.get(company_id)
    portal = company.own_portal

    if action == 'load':
        ret = {'company': company.get_client_side_dict(),
               'portal': portal.get_client_side_dict(more_fields='tags,divisions.tags')}
        for division in ret['portal']['divisions']:
            division['tags'] = {tagdict['id']: True for tagdict in division['tags']}
        return ret
    else:
        if action == 'save':
            return {}
        else:
            return {'errors': {}, 'warnings': {}, 'notices': {}}
