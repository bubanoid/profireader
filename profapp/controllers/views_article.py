from flask import render_template, g

from profapp.models.portal import PortalDivision, Portal, MemberCompanyPortal

from .blueprints_declaration import article_bp
from .request_wrapers import check_right
from .. import utils
from ..models.company import Company
from ..models.materials import Material, Publication
from ..models.pr_base import PRBase, Grid
from ..models.rights import EditOrSubmitMaterialInPortal, PublishUnpublishInPortal, EditMaterialRight, \
    EditPublicationRight, UserIsEmployee, UserIsActive, BaseRightsEmployeeInCompany
from ..models.tag import Tag


@article_bp.route('/<string:company_id>/material_update/<string:material_id>/', methods=['GET'])
# @article_bp.route('/<string:company_id>/publication_update/<string:publication_id>/', methods=['GET'])
@article_bp.route('/<string:company_id>/material_create/', methods=['GET'])
# @check_right(EditMaterialRight, ['material_id'])
# @check_right(EditPublicationRight, ['publication_id', 'company_id'])
# @check_right(BaseRightsEmployeeInCompany, ['company_id'], BaseRightsEmployeeInCompany.ACTIONS['CREATE_MATERIAL'])
def article_show_form(material_id=None, company_id=None):
    company = Company.get(company_id)
    return render_template('article/form.html', material_id=material_id, company_id=company_id, company=company)


@article_bp.route('/<string:company_id>/material_update/<string:material_id>/', methods=['OK'])
# @article_bp.route('/<string:company_id>/publication_update/<string:publication_id>/', methods=['OK'])
@article_bp.route('/<string:company_id>/material_create/', methods=['OK'])
# @check_right(EditMaterialRight, ['material_id'])
# @check_right(EditPublicationRight, ['publication_id', 'company_id'])
# @check_right(BaseRightsEmployeeInCompany, ['company_id'], BaseRightsEmployeeInCompany.ACTIONS['CREATE_MATERIAL'])
def load_form_create(json_data, company_id=None, material_id=None):
    action = g.req('action', allowed=['load', 'validate', 'save'])

    if material_id:
        material = Material.get(material_id)
    else:
        material = Material(company=Company.get(company_id), company_id=company_id, editor=g.user)

    if action == 'load':
        return {'material': material.get_client_side_dict(more_fields='long|company|illustration')}
    else:
        parameters = utils.filter_json(json_data, 'material.title|subtitle|short|long|keywords|author')
        material.attr(parameters['material'])
        if action == 'validate':
            material.detach()
            return material.validate(material.id is not None)
        else:
            material.save()
            material.illustration = json_data['material']['illustration']

            return {'material': material.save().get_client_side_dict(more_fields='long|company|illustration')}


@article_bp.route('/material_details/<string:material_id>/', methods=['GET'])
# @check_right(UserIsEmployee, ['material_id'])
def material_details(material_id):
    company = Company.get(Material.get(material_id).company.id)
    return render_template('company/material_details.html',
                           article=Material.get(material_id).get_client_side_dict(),
                           company=company)


def get_portal_dict_for_material(portal, company, material=None, publication=None, submit=None):
    ret = {}
    ret['portal'] = portal.get_client_side_dict(
        fields='id, name, host, logo.url, divisions.id|name|portal_division_type_id, own_company.name|id, own_company.logo.url')

    
    ret['divisions'] = PRBase.get_ordered_dict([d for d in ret['portal']['divisions'] if (
        d['portal_division_type_id'] == 'events' or d['portal_division_type_id'] == 'news')])
    ret['company_id'] = company.id
    if material:
        publication_in_portal = utils.db.query_filter(Publication).filter_by(material_id=material.id).filter(
            Publication.portal_division_id.in_(
                [div_id for div_id, div in ret['divisions'].items()])).first()
    else:
        publication_in_portal = publication
    if publication_in_portal:
        if submit:
            ret['replace_id'] = publication_in_portal.id
        ret['id'] = portal.id if submit else publication_in_portal.id
        ret['publication'] = publication_in_portal.get_client_side_dict(
            'id,status,visibility,portal_division_id,publishing_tm')
        ret['publication']['portal_division'] = ret['divisions'][ret['publication']['portal_division_id']]
        ret['publication']['counts'] = '0/0/0/0'
        ret['actions'] = PublishUnpublishInPortal(publication=publication_in_portal,
                                                  division=publication_in_portal.portal_division, company=company).actions()

    else:
        ret['id'] = portal.id
        ret['publication'] = None
        ret['actions'] = {EditOrSubmitMaterialInPortal.ACTIONS['SUBMIT']:
                              EditOrSubmitMaterialInPortal(material=material, portal=portal).actions()[
                                  EditOrSubmitMaterialInPortal.ACTIONS['SUBMIT']]}

    return ret


@article_bp.route('/material_details/<string:material_id>/', methods=['OK'])
# @check_right(UserIsEmployee, ['material_id'])
def material_details_load(json, material_id):
    material = Material.get(material_id)
    company = material.company

    return {
        'material': material.get_client_side_dict(more_fields='long'),
        'actions': {EditOrSubmitMaterialInPortal.ACTIONS['EDIT']:
                        EditMaterialRight(material=material, portal=company.own_portal).is_allowed()},
        'company': company.get_client_side_dict(),
        'portals': {
            'grid_data': [get_portal_dict_for_material(portal, company, material) for portal in
                          PublishUnpublishInPortal.get_portals_where_company_is_member(company)],
            'grid_filters': {
                'publication.status': Grid.filter_for_status(Publication.STATUSES)
            }

        }
    }


@article_bp.route('/submit_publish/<string:article_action>/', methods=['OK'])
@check_right(UserIsActive)
def submit_publish(json, article_action):
    action = g.req('action', allowed=['load', 'validate', 'save'])
    company = Company.get(json['company']['id'])
    if article_action == 'SUBMIT':
        material = Material.get(json['material']['id'])
        check = EditOrSubmitMaterialInPortal(material=material, portal=json['portal']['id']).action_is_allowed(
            article_action)
        if check != True:
            return check
        publication = Publication(material=material)
        more_data_to_ret = {
            'material': {'id': material.id},
            'can_material_also_be_published': check == True
        }
    else:
        publication = Publication.get(json['publication']['id'])
        check = PublishUnpublishInPortal(publication=publication, division=publication.portal_division_id,
                                         company=company).action_is_allowed(article_action)
        if check != True:
            return check
        more_data_to_ret = {}

    if action == 'load':
        portal = Portal.get(json['portal']['id'])
        membership = MemberCompanyPortal.get_by_portal_id_company_id(portal.id, company.id)
        ret = {
            'publication': publication.get_client_side_dict(),
            'company': company.get_client_side_dict(),
            'membership': membership.get_client_side_dict(fields = 'current_membership_plan_issued'),
            'publication_count': membership.get_publication_count(),
            'portal': portal.get_client_side_dict(fields = 'id,name,tags')
        }
        ret['portal']['divisions'] = PRBase.get_ordered_dict(
            PublishUnpublishInPortal().get_active_division(portal.divisions))

        return utils.dict_merge(ret, more_data_to_ret)
    else:

        # publication.attr(g.filter_json(json['publication'], 'portal_division_id'))
        publication.portal_division = PortalDivision.get(json['publication']['portal_division_id'], returnNoneIfNotExists=True)
        publication.visibility = json['publication']['visibility']
        # publication.division = PortalDivision.get(json['publication']['portal_division_id'])
        publication.publishing_tm = PRBase.parse_timestamp(json['publication'].get('publishing_tm'))
        publication.event_begin_tm = PRBase.parse_timestamp(json['publication'].get('event_begin_tm'))
        publication.event_end_tm = PRBase.parse_timestamp(json['publication'].get('event_end_tm'))
        publication.tags = [Tag.get(t['id']) for t in json['publication']['tags']]

        publication.status = PublishUnpublishInPortal.STATUSES['SUBMITTED']

        if 'also_publish' in json and json['also_publish']:
            publication.status = PublishUnpublishInPortal.STATUSES['PUBLISHED']
        else:
            if article_action in [PublishUnpublishInPortal.ACTIONS['PUBLISH'],
                                  PublishUnpublishInPortal.ACTIONS['REPUBLISH']]:
                publication.status = PublishUnpublishInPortal.STATUSES['PUBLISHED']
            elif article_action in [PublishUnpublishInPortal.ACTIONS['UNPUBLISH'],
                                    PublishUnpublishInPortal.ACTIONS['UNDELETE']]:
                publication.status = PublishUnpublishInPortal.STATUSES['UNPUBLISHED']
            elif article_action in [PublishUnpublishInPortal.ACTIONS['DELETE']]:
                publication.status = PublishUnpublishInPortal.STATUSES['DELETED']

        if action == 'validate':
            publication.detach()
            return (publication.validate(True if article_action == 'SUBMIT' else False)
                    if (
                article_action in ['SUBMIT', 'PUBLISH', 'REPUBLISH']) else publication.DEFAULT_VALIDATION_ANSWER())
        else:
            # if article_action == 'SUBMIT':
            #     publication.long = material.clone_for_portal_images_and_replace_urls(publication.portal_division_id,
            #                                                                          publication)
            publication.save()

            g.db().execute("SELECT tag_publication_set_position('%s', ARRAY ['%s']);" %
                           (publication.id, "', '".join([t.id for t in publication.tags])))

            return get_portal_dict_for_material(publication.portal_division.portal, company, publication=publication,
                                                submit=article_action == 'SUBMIT')

# @article_bp.route('/list_reader')
# @article_bp.route('/list_reader/<int:page>/')
# @check_right(UserIsActive)
# def list_reader(page=1):
#     search_text = request.args.get('search_text') or ''
#     favorite = 'favorite' in request.args
#     if not favorite:
#         articles, pages, page = Search().search({'class': Publication,
#                                                  'filter': and_(Publication.portal_division_id ==
#                                                                 db(PortalDivision).filter(
#                                                                     PortalDivision.portal_id ==
#                                                                     db(UserPortalReader,
#                                                                        user_id=g.user.id).subquery().
#                                                                     c.portal_id).subquery().c.id,
#                                                                 Publication.status ==
#                                                                 Publication.STATUSES['PUBLISHED']),
#                                                  'tags': True, 'return_fields': 'default_dict'}, page=page)
#     else:
#         articles, pages, page = Search().search({'class': Publication,
#                                                  'filter': (Publication.id == db(ReaderPublication,
#                                                                                  user_id=g.user.id,
#                                                                                  favorite=True).subquery().c.
#                                                             publication_id),
#                                                  'tags': True, 'return_fields': 'default_dict'}, page=page,
#                                                 search_text=search_text)
#     portals = UserPortalReader.get_portals_for_user() if not articles else None
#
#     return render_template('partials/reader/reader_base.html',
#                            articles=articles,
#                            pages=pages,
#                            current_page=page,
#                            page_buttons=Config.PAGINATION_BUTTONS,
#                            portals=portals,
#                            favorite=favorite
#                            )
