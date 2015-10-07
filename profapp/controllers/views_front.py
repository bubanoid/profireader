from .blueprints import front_bp
from flask import render_template, request, url_for, redirect, g, current_app
from ..models.articles import Article, ArticlePortal
from ..models.portal import CompanyPortal, PortalDivision, Portal, Company, PortalDivisionSettings_company_subportal
from config import Config
# from profapp import
from .pagination import pagination
from sqlalchemy import Column, ForeignKey, text


def get_params(**argv):
    search_text = request.args.get('search_text') if request.args.get('search_text') else ''
    app = current_app._get_current_object()
    portal = g.db().query(Portal).filter_by(host=app.config['SERVER_NAME']).one()

    sub_query = Article.subquery_articles_at_portal(search_text=search_text, portal_id=portal.id)
    return search_text, portal, sub_query


def portal_and_settings(portal):

    ret = portal.get_client_side_dict()
    newd = []
    for di in ret['divisions']:
        if di['portal_division_type_id'] == 'company_subportal':
            pdset = g.db().query(PortalDivisionSettings_company_subportal).filter_by(portal_division_id=di['id']).one()
            com_port = g.db().query(CompanyPortal).get(pdset.company_portal_id)
            di['member_company'] = Company.get(com_port.company_id)
        newd.append(di)
    ret['divisions'] = newd
    return ret


@front_bp.route('/', methods=['GET'])
@front_bp.route('<int:page>/', methods=['GET'])
def index(page=1):
    search_text, portal, sub_query = get_params()
    division = g.db().query(PortalDivision).filter_by(portal_id=portal.id, portal_division_type_id='index').one()
    articles, pages, page = pagination(query=sub_query, page=page)

    return render_template('front/bird/index.html',
                           articles={a.id:
                                         dict(list(a.get_client_side_dict().items()) +
                                              list({'main_tags': {'foo': 'one_tag'}}.items()))
                                     for a in articles},
                           portal=portal_and_settings(portal),
                           current_division=division.get_client_side_dict(),
                           pages=pages,
                           current_page=page,
                           page_buttons=Config.PAGINATION_BUTTONS,
                           search_text=search_text)


@front_bp.route('<string:division_name>/<string:search_text>', methods=['GET'])
@front_bp.route('<string:division_name>/<int:page>/<string:search_text>', methods=['GET'])
def division(division_name, search_text, page=1):
    search_text, portal, sub_query = get_params()
    division = g.db().query(PortalDivision).filter_by(portal_id=portal.id, name=division_name).one()
    if division.portal_division_type_id == 'news' or division.portal_division_type_id == 'events':

        sub_query = Article.subquery_articles_at_portal(search_text=search_text,
                                                        portal_division_id=division.id)
        articles, pages, page = pagination(query=sub_query, page=page)


        return render_template('front/bird/division.html',
                               articles={a.id: a.get_client_side_dict() for
                                         a in articles},
                               current_division=division.get_client_side_dict(),
                               portal=portal_and_settings(portal),
                               pages=pages,
                               current_page=page,
                               page_buttons=Config.PAGINATION_BUTTONS,
                               search_text=search_text)

    elif division.portal_division_type_id == 'catalog':

        # sub_query = Article.subquery_articles_at_portal(search_text=search_text,
        # articles, pages, page = pagination(query=sub_query, page=page)

        members = {member.company_id: Company.get(member.company_id).get_client_side_dict() for
                   member in division.portal.company_assoc}

        return render_template('front/bird/catalog.html',
                               members=members,
                               current_division=division.get_client_side_dict(),
                               portal=portal_and_settings(portal))

    else:
        return 'unknown division.portal_division_type_id = %s' % (division.portal_division_type_id,)


# TODO OZ by OZ: portal filter, move portal filtering to decorator

@front_bp.route('details/<string:article_portal_id>')
def details(article_portal_id):
    search_text, portal, sub_query = get_params()

    article = ArticlePortal.get(article_portal_id)
    article_dict = article.to_dict('id, title,short, cr_tm, md_tm, '
                                   'publishing_tm, keywords, status, long, image_file_id,'
                                   'division.name, division.portal.id,'
                                   'company.name')
    article_dict['tags'] = {'foo': 'one tag', 'bar': 'second tag'}

    division = g.db().query(PortalDivision).filter_by(id=article.portal_division_id).one()

    return render_template('front/bird/article_details.html',
                           portal=portal_and_settings(portal),
                           current_division=division.get_client_side_dict(),
                           article=article.to_dict('id, title,short, cr_tm, md_tm, '
                                                   'publishing_tm, status, long, image_file_id,'
                                                   'division.name, division.portal.id,'
                                                   'company.name'))


@front_bp.route('<string:division_name>/_c/<string:member_company_id>/<string:member_company_name>/')
@front_bp.route('<string:division_name>/_c/<string:member_company_id>/<string:member_company_name>/<int:page>/')

def subportal_division(division_name, member_company_id, member_company_name, page=1):

    member_company = Company.get(member_company_id)

    search_text, portal, sub_query = get_params()


    division = g.db().query(PortalDivision).filter_by(portal_id=portal.id, name=division_name).one()

    sub_query = Article.subquery_articles_at_portal(search_text=search_text,
                                                        portal_division_id=division.id).filter(Company.id == member_company_id)
    articles, pages, page = pagination(query=sub_query, page=page)

    return render_template('front/bird/subportal_division.html',
                           articles={a.id: a.get_client_side_dict() for
                                     a in articles},
                           subportal=True,
                           portal=portal_and_settings(portal),
                           current_division=division.get_client_side_dict(),
                           selected_division_id='index',
                           member_company = member_company.get_client_side_dict(),
                           pages=False,
                           current_page=page,
                           page_buttons=Config.PAGINATION_BUTTONS,
                           search_text=search_text)


@front_bp.route('_c/<string:member_company_id>/<string:member_company_name>/')
@front_bp.route('_c/<string:member_company_id>/<string:member_company_name>/<int:page>/')
def subportal(member_company_id, member_company_name, page=1):

    member_company = Company.get(member_company_id)

    search_text, portal, sub_query = get_params()
    sub_query = sub_query.filter(Company.id == member_company_id)

    division = g.db().query(PortalDivision).filter_by(portal_id=portal.id, portal_division_type_id='index').one()

    articles, pages, page = pagination(query=sub_query, page=page)

    return render_template('front/bird/subportal.html',
                           articles={a.id: a.get_client_side_dict() for
                                     a in articles},
                           subportal=True,
                           portal=portal_and_settings(portal),
                           current_division=division.get_client_side_dict(),
                           selected_division_id='index',
                           member_company = member_company.get_client_side_dict(),
                           pages=False,
                           current_page=page,
                           page_buttons=Config.PAGINATION_BUTTONS,
                           search_text=search_text)
