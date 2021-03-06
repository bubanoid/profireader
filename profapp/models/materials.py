from datetime import datetime

import simplejson
from flask import g, session, url_for
from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import and_, expression

from config import Config
from profapp import on_value_changed
from .elastic import PRElasticField, PRElasticDocument
from .files import FileImg, FileImgDescriptor
from .pr_base import PRBase, Base, Grid
from .. import utils
from ..constants.RECORD_IDS import FOLDER_AND_FILE
from ..constants.TABLE_TYPES import TABLE_TYPES
from ..models.company import Company, UserCompany
from ..models.portal import PortalDivision, Portal
from ..models.tag import Tag, TagPublication
from ..models.users import User


class Material(Base, PRBase, PRElasticDocument):
    __tablename__ = 'material'
    id = Column(TABLE_TYPES['id_profireader'], primary_key=True, nullable=False)
    # portal_id = Column(TABLE_TYPES['id_profireader'], ForeignKey('portal.id'))
    # portal_division_id = Column(TABLE_TYPES['id_profireader'], ForeignKey('portal_division.id'))

    # TODO: OZ by OZ: remove me
    _del_image_file_id = Column(TABLE_TYPES['id_profireader'], ForeignKey('file.id'), nullable=True)

    illustration_file_img_id = Column(TABLE_TYPES['id_profireader'], ForeignKey(FileImg.id), nullable=True)
    illustration_file_img = relationship(FileImg, uselist=False)

    illustration = FileImgDescriptor(relation_name='illustration_file_img',
                                     file_decorator=lambda m, r, f: f.attr(
                                         name='%s_for_material_illustration_%s' % (f.name, m.id),
                                         parent_id=m.company.system_folder_file_id,
                                         root_folder_id=m.company.system_folder_file_id),
                                     image_size=[600, 480],
                                     min_size=[600 / 6, 480 / 6],
                                     aspect_ratio=[600 / 480., 600 / 480.],
                                     no_selection_url=utils.fileUrl(FOLDER_AND_FILE.no_article_image()))

    cr_tm = Column(TABLE_TYPES['timestamp'])
    md_tm = Column(TABLE_TYPES['timestamp'])

    title = Column(TABLE_TYPES['name'], default='', nullable=False)
    subtitle = Column(TABLE_TYPES['subtitle'], default='', nullable=False)
    short = Column(TABLE_TYPES['text'], default='', nullable=False)
    long = Column(TABLE_TYPES['text'], default='', nullable=False)
    # long_stripped = Column(TABLE_TYPES['text'], nullable=False)

    keywords = Column(TABLE_TYPES['keywords'], nullable=False)
    author = Column(TABLE_TYPES['short_name'], nullable=False)

    status = Column(TABLE_TYPES['status'], default='NORMAL')
    STATUSES = {'NORMAL': 'NORMAL', 'EDITING': 'EDITING', 'FINISHED': 'FINISHED', 'DELETED': 'DELETED',
                 'APPROVED': 'APPROVED'}

    editor_user_id = Column(TABLE_TYPES['id_profireader'], ForeignKey('user.id'), nullable=False)
    editor = relationship(User, uselist=False)

    company_id = Column(TABLE_TYPES['id_profireader'], ForeignKey(Company.id))
    company = relationship(Company, uselist=False)

    publications = relationship('Publication', primaryjoin="Material.id==Publication.material_id",
                                cascade="save-update, merge, delete")

    # search_fields = {'title': {'relevance': lambda field='title': RELEVANCE.title},
    #                  'short': {'relevance': lambda field='short': RELEVANCE.short},
    #                  'long': {'relevance': lambda field='long': RELEVANCE.long},
    #                  'keywords': {'relevance': lambda field='keywords': RELEVANCE.keywords}}


    def is_active(self):
        return True

    def get_client_side_dict(self,
                             fields='id,cr_tm,md_tm,company_id,illustration.url,title,subtitle,author,short,long,keywords,company.id|name',
                             more_fields=None):
        return self.to_dict(fields, more_fields)

    def validate(self, is_new):
        ret = super().validate(is_new)
        if (self.omit_validation):
            return ret

        if ret['errors']:
            ret['errors']['_'] = 'You have some error'
        else:
            ret['notices']['_'] = 'Ok, you can click submit'

        return ret

    @staticmethod
    def subquery_company_materials(company_id=None, filters=None, sorts=None):
        sub_query = utils.db.query_filter(Material, company_id=company_id)
        return sub_query

    @staticmethod
    def get_material_grid_data(material):
        dict = material.get_client_side_dict(fields='cr_tm,md_tm,title,editor.full_name,id,illustration.url')
        dict.update({'portal.name': None if len(material.publications) == 0 else '', 'level': True})
        dict.update({'actions': None if len(material.publications) == 0 else '', 'level': True})
        list = [utils.dict_merge(
            publication.get_client_side_dict(fields='portal_division.portal.name|host,status, id, portal_division_id'),
            {
                #    'actions':
                #     {'edit': PublishUnpublishInPortal(publication=publication,
                #                                       division=publication.division, company=material.company)
                #         .actions()[PublishUnpublishInPortal.ACTIONS['EDIT']]
                #      } if publication.status != 'SUBMITTED' and publication.status != "DELETED" else {}
            },
            material.get_client_side_dict(fields='title')
        )
                for publication in material.publications]
        return dict, list

    @staticmethod
    def get_portals_where_company_send_article(company_id):
        portals = {}

        for m in utils.db.query_filter(Material, company_id=company_id).all():
            for pub in m.publications:
                portals[pub.portal_division.portal.id] = pub.portal_division.portal.name
        return portals

    @staticmethod
    def get_companies_which_send_article_to_portal(portal_id):
        # all = {'name': 'All', 'id': 0}
        companies = {}
        # companies.append(all)
        articles = g.db.query(Publication). \
            join(Publication.portal). \
            filter(Portal.id == portal_id).all()
        # for article in db(Publication, portal_id=portal_id).all():
        for article in articles:
            companies[article.company.id] = article.company.name
        return companies

        # def set_image_client_side_dict(self, client_data):
        #     if client_data['selected_by_user']['type'] == 'preset':
        #         client_data['selected_by_user'] = {'type': 'none'}
        #     if not self.company:
        #         folder_id = Company.get(self.company_id).system_folder_file_id
        #     else:
        #         folder_id = self.company.system_folder_file_id
        #
        #     FileImg.set_image_cropped_file(self.illustration_image_cropped, self.image_cropping_properties(),
        #                                    client_data, folder_id)
        #     return self

    @classmethod
    def __declare_last__(cls):
        cls.elastic_listeners(cls)

    def elastic_insert(self):
        pass

    def elastic_update(self):
        for p in self.publications:
            p.elastic_update()

    def elastic_delete(self):
        for p in self.publications:
            p.elastic_delete()


class ReaderPublication(Base, PRBase):
    __tablename__ = 'reader_publication'
    id = Column(TABLE_TYPES['id_profireader'], primary_key=True)
    user_id = Column(TABLE_TYPES['id_profireader'], ForeignKey('user.id'))
    publication_id = Column(TABLE_TYPES['id_profireader'], ForeignKey('publication.id'))
    favorite = Column(TABLE_TYPES['boolean'], default=False)
    liked = Column(TABLE_TYPES['boolean'], default=False)


class Publication(Base, PRBase, PRElasticDocument):
    __tablename__ = 'publication'
    # portal_id = Column(TABLE_TYPES['id_profireader'], ForeignKey('portal.id'))
    id = Column(TABLE_TYPES['id_profireader'], primary_key=True, nullable=False)

    material_id = Column(TABLE_TYPES['id_profireader'], ForeignKey('material.id'))
    material = relationship(Material, cascade="save-update, merge")

    cr_tm = Column(TABLE_TYPES['timestamp'])
    md_tm = Column(TABLE_TYPES['timestamp'])

    publishing_tm = Column(TABLE_TYPES['timestamp'])
    event_begin_tm = Column(TABLE_TYPES['timestamp'])
    event_end_tm = Column(TABLE_TYPES['timestamp'])

    read_count = Column(TABLE_TYPES['int'], default=0)
    like_count = Column(TABLE_TYPES['int'], default=0)

    tags = relationship(Tag, secondary='tag_publication', uselist=True,
                        order_by=lambda: expression.desc(TagPublication.position))

    status = Column(TABLE_TYPES['status'])

    STATUSES = {'SUBMITTED': 'SUBMITTED', 'UNPUBLISHED': 'UNPUBLISHED', 'PUBLISHED': 'PUBLISHED', 'DELETED': 'DELETED',
                'HOLDED': 'HOLDED'}

    visibility = Column(TABLE_TYPES['status'], default='OPEN')
    VISIBILITIES = {'OPEN': 'OPEN', 'REGISTERED': 'REGISTERED', 'PAYED': 'PAYED'}
    # , 'CONFIDENTIAL': 'CONFIDENTIAL'

    portal_division_id = Column(TABLE_TYPES['id_profireader'], ForeignKey('portal_division.id'))
    portal_division = relationship('PortalDivision', uselist=False)

    # portal = relationship('Portal',
    #                       secondary='portal_division',
    #                       primaryjoin="Publication.portal_division_id == PortalDivision.id",
    #                       secondaryjoin="PortalDivision.portal_id == Portal.id",
    #                       back_populates='publications',
    #                       uselist=False)

    company = relationship(Company, secondary='material',
                           primaryjoin="Publication.material_id == Material.id",
                           secondaryjoin="Material.company_id == Company.id",
                           viewonly=True, uselist=False)

    # elasticsearch begin
    def elastic_get_fields(self):
        return {
            'id': PRElasticField(analyzed=False, setter=lambda: self.id),

            'tags': PRElasticField(setter=lambda: ' '.join([t.text for t in self.tags])),
            'tag_ids': PRElasticField(analyzed=False, setter=lambda: [t.id for t in self.tags]),

            'status': PRElasticField(setter=lambda: self.status, analyzed=False),

            'company_id': PRElasticField(analyzed=False, setter=lambda: self.material.company_id),
            'company_name': PRElasticField(setter=lambda: self.material.company_id),

            'portal_id': PRElasticField(analyzed=False, setter=lambda: self.portal_division.portal_id),
            'portal_name': PRElasticField(setter=lambda: self.portal_division.portal.name),

            'division_id': PRElasticField(analyzed=False, setter=lambda: self.portal_division.id),
            'division_type': PRElasticField(analyzed=False,
                                            setter=lambda: self.portal_division.portal_division_type.id),
            'division_name': PRElasticField(setter=lambda: self.portal_division.name),

            'date': PRElasticField(ftype='date', setter=lambda: int(self.publishing_tm.timestamp() * 1000)),

            'title': PRElasticField(setter=lambda: self.material.title, boost=10),
            'subtitle': PRElasticField(setter=lambda: self.strip_tags(self.material.subtitle), boost=5),
            'keywords': PRElasticField(setter=lambda: self.material.keywords, boost=5),
            'short': PRElasticField(setter=lambda: self.strip_tags(self.material.short), boost=2),
            'long': PRElasticField(setter=lambda: self.strip_tags(self.material.long)),

            'author': PRElasticField(setter=lambda: self.strip_tags(self.material.author)),
            'address': PRElasticField(setter=lambda: ''),

            'custom_data': PRElasticField(analyzed=False,
                                          setter=lambda: simplejson.dumps({'material_id': self.material_id})),

        }

    def elastic_get_index(self):
        return 'front'

    def elastic_get_doctype(self):
        return 'article'

    def elastic_get_id(self):
        return self.id

    @classmethod
    def __declare_last__(cls):
        cls.elastic_listeners(cls)

    def is_active(self):
        return True

    def create_article(self):
        return utils.dict_merge(
            self.get_client_side_dict(
                more_fields='portal_division.portal_division_type_id,portal_division.portal.logo.url'),
            Material.get(self.material_id).get_client_side_dict(
                fields='long|short|title|subtitle|keywords|illustration|author'),
            {'social_activity': self.social_activity_dict()},
            remove={'material': True})

    # def like_dislike_user_article(self, liked):
    #     article = db(ReaderPublication, publication_id=self.id,
    #                  user_id=g.user.id if g.user else None).one()
    #     article.favorite = True if liked else False
    #     self.like_count += 1

    def seo_dict(self):
        return {
            'title': self.material.title,
            'keywords': ','.join(t.text for t in self.tags),
            'description': self.material.short if self.material.short else self.material.subtitle,
            'image_url': self.material.illustration['url'] if self.material.illustration['selected_by_user'][
                                                                  'type'] == 'provenance' else None
        }

    def search_filter_default(self, division_id, company_id=None):
        """ :param division_id: string with id from table portal_division,
                   optional company_id: string with id from table company. If provided
                   , this function will check if ArticleCompany has relation with our class.
            :return: dict with prepared filter parameters for search method """
        division = utils.db.query_filter(PortalDivision, id=division_id).one()
        division_type = division.portal_division_type.id
        visibility = Publication.visibility.in_(Publication.articles_visibility_for_user(
            portal_id=division.portal_id)[0])
        filter = None
        if division_type == 'index':
            filter = {'class': Publication,
                      'filter': and_(Publication.portal_division_id.in_(utils.db.query_filter(
                          PortalDivision.id, portal_id=division.portal_id).filter(
                          PortalDivision.portal_division_type_id != 'events'
                      )), Publication.status == Publication.STATUSES['PUBLISHED'], visibility),
                      'return_fields': 'default_dict', 'tags': True}
        elif division_type == 'news':
            if not company_id:
                filter = {'class': Publication,
                          'filter': and_(Publication.portal_division_id == division_id,
                                         Publication.status ==
                                         Publication.STATUSES['PUBLISHED'], visibility),
                          'return_fields': 'default_dict', 'tags': True}
            else:
                filter = {'class': Publication,
                          'filter': and_(Publication.portal_division_id == division_id,
                                         Publication.status ==
                                         Publication.STATUSES['PUBLISHED'],
                                         utils.db.query_filter(ArticleCompany, company_id=company_id,
                                                               id=Publication.article_company_id).exists(), visibility),
                          'return_fields': 'default_dict', 'tags': True}
        elif division_type == 'events':
            if not company_id:
                filter = {'class': Publication,
                          'filter': and_(Publication.portal_division_id == division_id,
                                         Publication.status ==
                                         Publication.STATUSES['PUBLISHED'], visibility),
                          'return_fields': 'default_dict', 'tags': True}
            else:
                filter = {'class': Publication,
                          'filter': and_(Publication.portal_division_id == division_id,
                                         Publication.status ==
                                         Publication.STATUSES['PUBLISHED'],
                                         utils.db.query_filter(ArticleCompany, company_id=company_id,
                                                               id=Publication.article_company_id).exists(), visibility),
                          'return_fields': 'default_dict', 'tags': True}
        return filter

    @staticmethod
    def articles_visibility_for_user(portal_id):
        employer = True
        visibilities = Publication.VISIBILITIES.copy()
        if not utils.db.query_filter(UserCompany, user_id=getattr(g.user, 'id', None),
                                     status=UserCompany.STATUSES['EMPLOYMENT_ACTIVE']).filter(
                    UserCompany.company_id == utils.db.query_filter(Portal.company_owner_id, id=portal_id)).count():
            # visibilities.pop(Publication.VISIBILITIES['CONFIDENTIAL'])
            employer = False
        return visibilities.keys(), employer

    def article_visibility_details(self):
        # TODO: OZ by OZ: remove hardcded urls!
        actions = {Publication.VISIBILITIES['OPEN']: lambda: True,
                   Publication.VISIBILITIES['REGISTERED']:
                       lambda: True if getattr(g.user, 'id', False) else
                       dict(redirect_url='//' + Config.MAIN_DOMAIN + '/auth/login_signup',
                            message='This article can read only by users which are logged in.',
                            context='log in'),
                   Publication.VISIBILITIES['PAYED']: lambda:
                   dict(redirect_url='//' + Config.MAIN_DOMAIN + '/reader/buy_subscription',
                        message='This article can read only by users which bought subscription on this portal.',
                        context='buy subscription'),
                   # Publication.VISIBILITIES['CONFIDENTIAL']:
                   #     lambda portal_id=self.portal_division.portal.id: True if
                   #     Publication.articles_visibility_for_user(portal_id)[1] else
                   #     dict(redirect_url='//' + Config.MAIN_DOMAIN + '/auth/login_signup',
                   #          message='This article can read only employees of this company.',
                   #          context='login as employee')
                   }
        return actions[self.visibility]()

    def get_client_side_dict(self, fields='id|read_count|tags|portal_division_id|cr_tm|md_tm|status|material_id|'
                                          'visibility|publishing_tm|event_begin_tm,event_end_tm,company.id|name, '
                                          'portal_division.id|name|portal_id, portal_division.portal.id|name|host, material',
                             more_fields=None):
        return self.to_dict(fields, more_fields)

    @staticmethod
    def update_article_portal(publication_id, **kwargs):
        utils.db.query_filter(Publication, id=publication_id).update(kwargs)

    @staticmethod
    def subquery_portal_articles(portal_id, filters, sorts):
        sub_query = utils.db.query_filter(Publication)
        list_filters = []
        list_sorts = []
        if 'publication_status' in filters:
            list_filters.append(
                {'type': 'select', 'value': filters['publication_status'], 'field': Publication.status})
        if 'company' in filters:
            sub_query = sub_query.join(Publication.company)
            list_filters.append({'type': 'select', 'value': filters['company'], 'field': Company.id})
        if 'date' in filters:
            list_filters.append(
                {'type': 'date_range', 'value': filters['date'], 'field': Publication.publishing_tm})
        sub_query = sub_query. \
            join(Publication.portal_division). \
            join(PortalDivision.portal). \
            filter(Portal.id == portal_id)
        if 'title' in filters:
            list_filters.append({'type': 'text', 'value': filters['title'], 'field': Publication.title})
        if 'date' in sorts:
            list_sorts.append({'type': 'date', 'value': sorts['date'], 'field': Publication.publishing_tm})
        else:
            list_sorts.append({'type': 'date', 'value': 'desc', 'field': Publication.publishing_tm})
        sub_query = Grid.subquery_grid(sub_query, list_filters, list_sorts)
        return sub_query

    def position_unique_filter(self):
        return and_(Publication.portal_division_id == self.portal_division_id,
                    Publication.position != None)

    def validate(self, is_new):
        ret = super().validate(is_new)
        if (self.omit_validation):
            return ret

        if not self.publishing_tm:
            ret['errors']['publishing_tm'] = 'Please select publication date'

        if not self.visibility in self.VISIBILITIES:
            ret['errors']['visibility'] = 'Please select publication visibility'

        if not self.portal_division_id and not self.portal_division:
            ret['errors']['portal_division_id'] = 'Please select portal division'
        else:
            portalDivision = PortalDivision.get(
                self.portal_division_id if self.portal_division_id else self.portal_division.id)
            if portalDivision.portal_division_type_id == 'events':
                if not self.event_begin_tm:
                    ret['errors']['event_begin_tm'] = 'Please select event start date'
                elif self.event_begin_tm and datetime.now() > self.event_begin_tm:
                    ret['warnings']['event_begin_tm'] = 'Event start time in past'

                if not self.event_end_tm:
                    ret['errors']['event_end_tm'] = 'Please select event end date'
                elif self.event_end_tm and self.event_begin_tm and self.event_begin_tm > self.event_end_tm:
                    ret['warnings']['event_end_tm'] = 'Event end time before event begin time'

        if ret['errors']:
            ret['errors']['_'] = 'You have some error'
        else:
            ret['notices']['_'] = 'Ok, you can click submit'

        return ret

    def set_tags_positions(self):
        tag_position = 0
        for tag in self.tags:
            tag_position += 1
            tag.position = tag_position
            # tag_pub = db(TagPublication).filter(and_(TagPublication.tag_id == tag.id,
            #                                          TagPublication.publication_id == self.id)).one()
            # tag_pub.position = tag_position
            # tag_pub.save()
        return self

    def get_related_articles(self, count=5):
        from sqlalchemy.sql import func

        return g.db().query(Publication).filter(
            and_(Publication.id != self.id,
                 Publication.portal_division_id.in_(
                     utils.db.query_filter(PortalDivision.id).filter(
                         PortalDivision.portal_id == self.portal_division.portal_id))
                 )).order_by(func.random()).limit(count).all()

    def add_to_read(self):
        if g.user and g.user.id:
            was_readed = utils.db.query_filter(ReaderPublication, user_id=g.user.id, publication_id=self.id).first()
            if not was_readed:
                was_readed = ReaderPublication(user_id=g.user.id, publication_id=self.id).save()
            return was_readed
        else:
            read = session.get('recently_read_articles', [])
            if self.id not in read:
                read.append(self.id)
                self.read_count += 1
                session['recently_read_articles'] = read
            return False

    def add_delete_favorite(self, favorite):
        reader_publication = self.add_to_read()
        reader_publication.favorite = True if favorite else False
        reader_publication.save()
        return self

    def add_delete_like(self, like):
        reader_publication = self.add_to_read()
        reader_publication.liked = True if like else False
        reader_publication.save()
        return self

    def is_favorite(self, user_id=None):
        return True if utils.db.query_filter(ReaderPublication,
                                             user_id=user_id if user_id else g.user.id if g.user else None,
                                             publication_id=self.id, favorite=True).first() else False

    def is_liked(self, user_id=None):
        return True if utils.db.query_filter(ReaderPublication,
                                             user_id=user_id if user_id else g.user.id if g.user else None,
                                             publication_id=self.id, liked=True).first() else False

    def liked_count(self):
        return utils.db.query_filter(ReaderPublication, publication_id=self.id, liked=True).count()

    def favorite_count(self):
        return utils.db.query_filter(ReaderPublication, publication_id=self.id, favorite=True).count()

    def social_activity_dict(self):
        return {
            'favorite': self.is_favorite(),
            'favorite_count': self.favorite_count(),
            'liked': self.is_liked(),
            'liked_count': self.liked_count()
        }

# TODO: OZ by OZ: cjange it to explicity function call
@on_value_changed(Publication.status)
def publication_status_changed(target: Publication, old_status, new_status, action):
    from ..models.translate import Phrase
    from ..models.portal import MemberCompanyPortal
    from ..models.permissions import RIGHT_AT_COMPANY




    portal_division = target.portal_division if target.portal_division else PortalDivision.get(
        target.portal_division_id)
    portal = portal_division.portal
    material = Material.get(target.material_id)

    right_at_company = None
    right_at_portal = None
    if new_value == Publication.STATUSES['SUBMITTED'] and not old_value:
        right_at_company = [RIGHT_AT_COMPANY.ARTICLES_SUBMIT_OR_PUBLISH,
                               RIGHT_AT_COMPANY.ARTICLES_UNPUBLISH]
        right_at_portal = [RIGHT_AT_COMPANY.ARTICLES_SUBMIT_OR_PUBLISH,
                              RIGHT_AT_COMPANY.ARTICLES_UNPUBLISH]
    elif new_value == Publication.STATUSES['PUBLISHED']:
        right_at_company = [RIGHT_AT_COMPANY.ARTICLES_SUBMIT_OR_PUBLISH,
                               RIGHT_AT_COMPANY.ARTICLES_UNPUBLISH]
        right_at_portal = [RIGHT_AT_COMPANY.ARTICLES_SUBMIT_OR_PUBLISH,
                              RIGHT_AT_COMPANY.ARTICLES_UNPUBLISH]
    elif old_value == Publication.STATUSES['PUBLISHED']:
        right_at_company = [RIGHT_AT_COMPANY.ARTICLES_SUBMIT_OR_PUBLISH,
                               RIGHT_AT_COMPANY.ARTICLES_UNPUBLISH]
        right_at_portal = [RIGHT_AT_COMPANY.ARTICLES_SUBMIT_OR_PUBLISH,
                              RIGHT_AT_COMPANY.ARTICLES_UNPUBLISH]

    target.notifications_about_employment_changes(
        what_happened="changed status of publication from %s to %s in behalf of %s" % (old_status, new_status, changed_by),
        rights_at_company=RIGHT_AT_COMPANY.EMPLOYEE_ENLIST_OR_FIRE)()

    if right_at_company or right_at_portal:
        membership = MemberCompanyPortal.get_by_portal_id_company_id(target.portal_division.portal_id,
                                                                     target.material.company_id)
        return membership.send_notifications_about_employment_changes(
            "changed status of %%(url_external_publication)s from %s to %s at division `%%(division_name)s`" %
            (old_value, new_value),
            additional_dict={
                'url_external_publication': portal.host + url_for('front.article_details', publication_id=target.id,
                                                                  publication_title=material.title),
                'division_name': portal_division.nameid_url(target.id, 'portal.publications', portal_id=portal.id)
            },
            rights_at_company=right_at_company,
            more_phrases_to_company=Phrase("See company`s %(url_company_materials)s", dict={
                'url_company_materials': utils.jinja.grid_url(material.id, 'company.materials',
                                                              company_id=material.company_id)}),
            right_at_portal=right_at_portal,
            more_phrases_to_portal=Phrase("See portal`s %(url_portal_publications)s", dict={
                'url_portal_publications': utils.jinja.grid_url(target.id, 'portal.publications', portal_id=portal.id)})
        )
    else:
        return utils.do_nothing()
