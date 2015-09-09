from .blueprints import company_bp
from ..models.company import simple_permissions
#from .request_wrapers import json
from flask.ext.login import login_required, current_user
from flask import render_template, request, url_for, g, redirect
from ..models.company import Company, UserCompany, Right
# from phonenumbers import NumberParseException
from ..constants.USER_ROLES import RIGHTS
from ..models.users import User
from .request_wrapers import ok, check_rights, from_request
from ..constants.STATUS import STATUS
from flask.ext.login import login_required
from ..models.articles import Article
from ..constants.ARTICLE_STATUSES import ARTICLE_STATUS_IN_COMPANY
from ..models.portal import CompanyPortal
from ..models.articles import ArticleCompany
from utils.db_utils import db
from ..models.rights import list_of_RightAtomic_attributes
from flask.ext.login import current_user


# todo (AA to OZ): is @json necessary here?
@company_bp.route('/search_to_submit_article/', methods=['POST'])
# @json
def search_to_submit_article(json):
    companies = Company().search_for_company(g.user_dict['id'],
                                             json['search'])
    return companies


@company_bp.route('/', methods=['GET'])
#@check_rights(simple_permissions(frozenset()))
@login_required
def show():
    return render_template('company/companies.html')


@company_bp.route('/', methods=['POST'])
#@check_rights(simple_permissions(frozenset()))
@ok
def load_companies(json):
    return {'companies': [employer.get_client_side_dict()
                          for employer in current_user.employers]}


@company_bp.route('/materials/<string:company_id>/', methods=['GET'])
#@check_rights(simple_permissions(frozenset()))
@login_required
def materials(company_id):
    return render_template('company/materials.html',
                           company_id={'id': company_id},
                           articles=[art.to_dict(
                               'id, title') for art in Article.
                               get_articles_submitted_to_company(
                                   company_id)])


@company_bp.route('/material_details/<string:company_id>/'
                  '<string:article_id>/', methods=['GET'])
#@check_rights(simple_permissions(frozenset()))
@login_required
def material_details(company_id, article_id):
    return render_template('company/material_details.html',
                           company_id=company_id, article_id=article_id)


@company_bp.route('/material_details/<string:company_id>/'
                  '<string:article_id>/', methods=['POST'])
@ok
def load_material_details(json, company_id, article_id):
    article = Article.get_one_article(article_id). \
        to_dict('id, title,short, cr_tm, md_tm, '
                'company_id, status, long,'
                'editor_user_id, company.name|id,'
                'portal_article.division.portal.id')
    portals = {port.id: port.to_dict('id, name, divisions.name|id')
               for port in CompanyPortal.get_portals(company_id)}
    if article['portal_article'] and \
            article['portal_article']['division']:
        portals = [port for port in portals if port['id'] !=
                   article['portal_article']['division']
                   ['portal']['id']]

    status = ARTICLE_STATUS_IN_COMPANY.can_user_change_status_to(
        article['status'])

    return {'article': article, 'status': status, 'portals':
        portals, 'company': Company.get(company_id).
        to_dict('id, employee.id|profireader_name'),
            'selected_portal': {}, 'selected_division': {}}


@company_bp.route('/update_article/', methods=['POST'])
@login_required
@ok
def update_article(json):

    ArticleCompany.update_article(
        company_id=json['comp']['id'], article_id=json['article']['id'],
        **{'status': json['article']['status']})
    return json

@company_bp.route('/submit_to_portal/', methods=['POST'])
@login_required
@ok
def submit_to_portal(json):

    article = ArticleCompany.get(json['article']['id'])
    article.clone_for_portal(json['selected_division'])
    return json

@company_bp.route('/add/')
#@check_rights(simple_permissions(frozenset()))
@login_required
def add():
    return render_template('company/company_add.html', user=g.user_dict)


@company_bp.route('/confirm_add/', methods=['POST'])
#@check_rights(simple_permissions(frozenset()))
@ok
def confirm_add(json):
    return Company(**json).create_new_company(g.user.id).\
        get_client_side_dict()


@company_bp.route('/profile/<string:company_id>/')
#@check_rights(simple_permissions(frozenset()))
@login_required
def profile(company_id):
    company = db(Company, id=company_id).one()
    user_rights_int = current_user.employer_assoc.filter_by(
        company_id=company_id).one().rights

    user_rights_list = list(Right.transform_rights_into_set(
        user_rights_int))

    image = url_for('filemanager.get', file_id=company.logo_file) if \
        company.logo_file else ''

    return render_template('company/company_profile.html',
                           company=company,
                           user_rights=user_rights_list,
                           image=image,
                           company_id=company_id
                           )


@company_bp.route('/employees/<company_id>/')
@check_rights(simple_permissions(frozenset(), from_request))
@login_required
def employees(company_id):
    company_user_rights = UserCompany.show_rights(company_id)

    for user_id in company_user_rights.keys():
        rights = company_user_rights[user_id]['rights']
        rez = {}
        for elem in list_of_RightAtomic_attributes:
            rez[elem.lower()] = True if elem.lower(
            ) in rights else False
        company_user_rights[user_id]['rights'] = rez

    user_id = current_user.get_id()
    curr_user = {user_id: company_user_rights[user_id]}
    current_company = db(Company, id=company_id).one()

    return render_template('company/company_employees.html',
                           company=current_company,
                           company_id=company_id,
                           company_user_rights=company_user_rights,
                           curr_user=curr_user,
                           Right=Right
                           )


@company_bp.route('/update_rights', methods=['POST'])
#@check_rights(simple_permissions(frozenset(['manage_access_company'])))
@login_required
def update_rights():
    data = request.form
    new_rights=data.getlist('right')
    UserCompany.update_rights(user_id=data['user_id'],
                              company_id=data['company_id'],
                              new_rights=data.getlist('right')
                              )
    return redirect(url_for('company.employees',
                            company_id=data['company_id']))


# todo: it must be checked!!!
@company_bp.route('/edit/<string:company_id>/')
#@check_rights(simple_permissions(frozenset(['manage_access_company',
#                                            'edit'])))
@login_required
def edit(company_id):
    company = db(Company, id=company_id).one()
    user = current_user  # # or is it UserCompany instance?
    return render_template('company/company_edit.html',
                           company=company,
                           user_query=user
                           )


@company_bp.route('/confirm_edit/<string:company_id>', methods=['POST'])
#@check_rights(simple_permissions(frozenset(['add_employee'])))
@login_required
def confirm_edit(company_id):
    Company().update_comp(company_id=company_id, data=request.form,
                          passed_file=request.files['logo_file'])
    return redirect(url_for('company.profile', company_id=company_id))


@company_bp.route('/subscribe/<string:company_id>/')
#@check_rights(simple_permissions(frozenset()))
@login_required
def subscribe(company_id):
    company_role = UserCompany(user_id=g.user_dict['id'],
                            company_id=company_id,
                            status=STATUS().NONACTIVE())
    company_role.subscribe_to_company()

    return redirect(url_for('company.profile', company_id=company_id))


@company_bp.route('/search_for_company_to_join/', methods=['POST'])
#@check_rights(simple_permissions(frozenset()))
@ok
def search_for_company_to_join(json):
    companies = Company().search_for_company_to_join(g.user_dict['id'],
                                                     json['search'])
    return companies


@company_bp.route('/join_to_company/<string:company_id>/',
                  methods=['POST'])
#@check_rights(simple_permissions(frozenset()))
@ok
def join_to_company(json, company_id):
    company_role = UserCompany(user_id=g.user_dict['id'],
                            company_id=json['company_id'],
                            status=STATUS().NONACTIVE())
    company_role.subscribe_to_company()
    return {'companies': [employer.get_client_side_dict()
                          for employer in current_user.employers]}



@company_bp.route('/add_subscriber/', methods=['POST'])
#@check_rights(simple_permissions(frozenset(['add_employee'])))
@login_required
def confirm_subscriber():
    company_role = UserCompany()
    data = request.form
    company_role.apply_request(company_id=data['company_id'],
                            user_id=data['user_id'],
                            bool=data['req'])
    return redirect(url_for('company.profile',
                            company_id=data['company_id']))


@company_bp.route('/suspend_employee/', methods=['POST'])
#@check_rights(simple_permissions(frozenset(['suspend_employee'])))
@login_required
def suspend_employee():
    data = request.form
    UserCompany.suspend_employee(user_id=data['user_id'],
                                 company_id=data['company_id'])
    return redirect(url_for('company.employees',
                            company_id=data['company_id']))


# todo: what actually is it intended?
@company_bp.route('/suspended_employees/<string:company_id>')
#@check_rights(simple_permissions(frozenset()))
@login_required
def suspended_employees_func(company_id):
    company = Company.query_company(company_id=company_id)
    suspended_employees = \
        UserCompany.suspend_employee(company_id,
                                     user_id=current_user.get_id())
    return render_template('company/company_suspended.html',
                           suspended_employees=suspended_employees,
                           company_id=company_id
                           )
