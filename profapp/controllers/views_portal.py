from .blueprints import portal_bp
from flask import render_template, g
from ..models.company import Company
from flask.ext.login import current_user, login_required
from ..models.portal import PortalDivisionType
from utils.db_utils import db
from ..models.portal import CompanyPortal, Portal, PortalLayout, PortalDivision
from .request_wrapers import ok, check_rights
from ..models.articles import ArticlePortal
from ..models.company import simple_permissions
from ..models.rights import Right
from profapp.models.rights import RIGHTS
from ..controllers import errors
from flask import request, Response


@portal_bp.route('/create/<string:company_id>/', methods=['GET'])
@login_required
def create_template(company_id):
    return render_template('company/portal_create.html', company_id=company_id)


@portal_bp.route('/<any(create,update):action>/<string:company_id>/', methods=['POST'])
@login_required
# @check_rights(simple_permissions([Right[RIGHTS.MANAGE_ACCESS_PORTAL()]]))
@ok
def create_load(json, action, state, company_id):

    if action == 'create':
        valid = Portal(name=json['name'], host=json['host'],
                   portal_layout_id=json['portal_layout_id'],
                   company_owner_id=company_id,
                   divisions=[PortalDivision(**division) for division in json['divisions']]) \
                    .create_portal().validate()
        if state == 'validate':
            # TODO OZ by OZ: next line is disgusting!!!!
            getattr(g, 'db', None).rollback()
            return valid
        elif len(valid['errors'].keys()):
            raise errors.ValidationException(valid)
        else:
            return Response(headers={'Location: http://google.com/'})
    else:
        return {}


@portal_bp.route('/<any(create,update):action>/<any(validate,save):state>/<string:company_id>/',
                 methods=['POST'])
@login_required
@ok
def create_save(json, action, state, company_id):
    layouts = [x.get_client_side_dict() for x in db(PortalLayout).all()]

    ret = {
        'company_id': company_id,
        'layouts': layouts,
        'division_types': {x.id: x.get_client_side_dict() for x in
                           PortalDivisionType.get_division_types()}
    }

    if action == 'create':
        ret['portal'] = {'company_id': company_id, 'name': '', 'host': '',
                         'portal_layout_id': layouts[0]['id'],
                         'divisions': [
                             {'name': 'index page', 'portal_division_type_id': 'index'},
                             {'name': 'news', 'portal_division_type_id': 'news'},
                             {'name': 'events', 'portal_division_type_id': 'events'},
                             {'name': 'catalog', 'portal_division_type_id': 'catalog'},
                             {'name': 'about', 'portal_division_type_id': 'about'},
                         ]}
    else:
        ret['portal'] = {}

    return ret


@portal_bp.route('/save/<string:company_id>/', methods=['POST'])
@login_required
# @check_rights(simple_permissions([Right[RIGHTS.MANAGE_ACCESS_PORTAL()]]))
@ok
def create_load(json, company_id):
    state = request.headers.get('state')
    if state in ['validate', 'send']:
        valid = Portal(name=json['name'], host=json['host'],
                       portal_layout_id=json['portal_layout_id'],
                       company_owner_id=company_id,
                       divisions=[PortalDivision(**division) for division in json['divisions']]) \
            .create_portal().validate()
        if state == 'validate':
            # TODO OZ by OZ: next line is disgusting!!!!
            getattr(g, 'db', None).rollback()
            return valid
        elif len(valid['errors'].keys()):
            raise errors.ValidationException(valid)
        else:
            return Response(headers={'Location: http://google.com/'})
    else:
        layouts = [x.get_client_side_dict() for x in db(PortalLayout).all()]
        division_types = {x.id: x.get_client_side_dict() for x in
                          PortalDivisionType.get_division_types()}

        return {'company_id': company_id,
                'portal': {'company_id': company_id, 'name': '', 'host': '',
                           'portal_layout_id': layouts[0]['id'],
                           'divisions': [
                               {'name': 'index page', 'portal_division_type_id': 'index'},
                               {'name': 'news', 'portal_division_type_id': 'news'},
                               {'name': 'events', 'portal_division_type_id': 'events'},
                               {'name': 'catalog', 'portal_division_type_id': 'catalog'},
                               {'name': 'about', 'portal_division_type_id': 'about'},
                           ]},
                'layouts': layouts,
                'division_types': division_types
                }


@portal_bp.route('/', methods=['POST'])
@login_required
# @check_rights(simple_permissions([]))
@ok
def apply_company(json):
    CompanyPortal.apply_company_to_portal(company_id=json['company_id'],
                                          portal_id=json['portal_id'])
    return {'portals_partners': [portal.portal.to_dict(
        'name, company_owner_id,id') for portal in CompanyPortal.get_portals(json['company_id'])],
            'company_id': json['company_id']}


@portal_bp.route('/partners/<string:company_id>/', methods=['GET'])
@login_required
# @check_rights(simple_permissions([]))
def partners(company_id):
    return render_template('company/company_partners.html',
                           company_id=company_id
                           )


@portal_bp.route('/partners/<string:company_id>/', methods=['POST'])
@login_required
# @check_rights(simple_permissions([]))
@ok
def partners_load(json, company_id):
    portal = db(Company, id=company_id).one().own_portal
    companies_partners = [comp.to_dict('id, name') for comp in
                          portal.companies] if portal else []
    portals_partners = [port.portal.to_dict('name, company_owner_id, id')
                        for port in CompanyPortal.get_portals(
            company_id) if port]
    user_rights = list(g.user.user_rights_in_company(company_id))
    return {'portal': portal.to_dict('name') if portal else [],
            'companies_partners': companies_partners,
            'portals_partners': portals_partners,
            'company_id': company_id,
            'user_rights': user_rights}


@portal_bp.route('/search_for_portal_to_join/', methods=['POST'])
@ok
@login_required
# @check_rights(simple_permissions([]))
def search_for_portal_to_join(json, delme):
    portals_partners = Portal.search_for_portal_to_join(
        json['company_id'], json['search'])
    return portals_partners


@portal_bp.route('/publications/<string:company_id>/', methods=['GET'])
@login_required
# @check_rights(simple_permissions([]))
def publications(company_id):
    return render_template('company/portal_publications.html',
                           company_id=company_id)


@portal_bp.route('/publications/<string:company_id>/', methods=['POST'])
@login_required
# @check_rights(simple_permissions([]))
@ok
def publications_load(json, company_id):
    portal = db(Company, id=company_id).one().own_portal
    if portal:
        if not portal.divisions[0]:
            return {'divisions': [{'name': '',
                                   'article_portal': []}]}
        portal = [port.to_dict('name|id|portal_id,article_portal.'
                               'status|md_tm|cr_tm|title|long|short|id,'
                               'article_portal.'
                               'company_article.company.id|'
                               'name|short_description|email|phone') for
                  port in portal.divisions if port.article_portal]

    user_rights = list(g.user.user_rights_in_company(company_id))

    return {'portal': portal, 'new_status': '',
            'company_id': company_id, 'user_rights': user_rights}


@portal_bp.route('/update_article_portal/', methods=['POST'])
@login_required
# @check_rights(simple_permissions([]))
@ok
def update_article_portal(json):
    update = json['new_status'].split('/')
    ArticlePortal.update_article_portal(update[0], **{'status': update[1]})
    return json
