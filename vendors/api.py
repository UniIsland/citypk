# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division
import asyncore
import json
import logging
from vendors.base_handler import BaseHandler
import os

import tornado.httpserver
from tornado.web import RequestHandler
import tornado.websocket
import tornado.ioloop
import tornado.web
import tornado.options
from tornado.options import define, options
from util import get_first_url_from_string

from vendors.models import *
from vendors.sina_auth import login_required


LISTENERS = []
logger = logging.getLogger(__name__)

class RealtimeHandler(tornado.websocket.WebSocketHandler):
    def open(self, *args, **kargs):
        print('new connection')
        LISTENERS.append(self)

    def on_message(self, message):
        print(message)

    def on_close(self):
        LISTENERS.remove(self)

class BattleListHandler(BaseHandler):
  def get(self):
    self.set_header('Content-Type', 'application/json;charset=utf-8')
    battles = [b.to_dict() for b in Battle.get_list()]
    self.write(json.dumps(battles))

class BattleHandler(BaseHandler):
  def get(self, bf_id):
    self.set_header('Content-Type', 'application/json;charset=utf-8')
    self.write(json.dumps(Battle.objects.get(id=bf_id).to_dict(detail=True)))

class PostListHandler(BaseHandler):
  def get(self, bf_id, fighter):
    self.set_header('Content-Type', 'application/json;charset=utf-8')
    battle = Battle.objects.get(id=bf_id)
    self.write(json.dumps({
      'recent_posts': [p.to_dict() for p in Post.battle_posts(battle, int(fighter), 'recent')],
      'hottest_posts': [p.to_dict() for p in Post.battle_posts(battle, int(fighter), 'hottest')],
    }))

class PostMessageHandler(BaseHandler):
  @login_required
  def post(self):
    self.set_header('Content-Type', 'application/json;charset=utf-8')
    #data = json.loads(self.request.body)

    bf_id = self.get_argument('bf_id')
    fighter = int(self.get_argument('fighter'))
    comment = self.get_argument('comment')
    img = get_first_url_from_string(comment)
    if img:
      comment = comment.replace(img, '')
    weibo_id = str(self.session['me'].id)
    try:
      battle = Battle.objects.get(id=bf_id)
      user = User.objects.get(weibo_id=weibo_id)
    except Exception as ex:
      logger.error('error:%s', ex, exc_info=True)
      self.write(json.dumps({
        'post_id': None,
        'status': 0,
        'message': u'提交失败'
      }))
      return
    post = Post(
      battle = battle,
      author = user,
      fighter = int(fighter),
      comment = comment,
      photo_url = img
    )
    post.save()
    fighter_to_blood = 1 if fighter == 0 else 0

    post.battle.blood(fighter_to_blood, 15)
    
    logger.info('post success')
    pn('Fight: post a new message')

    self.write(json.dumps({
      'post_id': str(post.id),
      'status': 1,
      'message': ''
    }))


class PostVoteHandler(BaseHandler):
  @login_required
  def post(self):
    #data = json.loads(self.request.body)
    post_id = self.get_argument('post_id')
    #post_id = data.get('post_id')
    weibo_id=str(self.session['me'].id)
    user = User.objects.get(weibo_id=weibo_id)
    post = Post.objects.get(id=post_id)
    result = post.vote_by(user)
    if result:
      pn('fight')
      f = 1 if post.fighter == 0 else 0
      post.battle.blood(f, 10)

    self.set_header('Content-Type', 'application/json;charset=utf-8')
    self.write(json.dumps({
      'post_id': str(post.id),
      'status': result,
      'message': ''
    }))

def pn(message, update=False, winner=0, delta={}):
  for l in LISTENERS:
        l.write_message(json.dumps({
          'update':update,
          'broadcast':message,
          'winner':winner,
          'delta':delta
        }))
