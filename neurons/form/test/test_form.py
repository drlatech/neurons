#!/usr/bin/env python
# encoding: utf8
#
# This file is part of the Neurons project.
# Copyright (c), Burak Arslan <burak.arslan@arskom.com.tr>,
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the {organization} nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

from __future__ import absolute_import, print_function

import unittest
import logging

from decimal import Decimal as D
from datetime import date, time, datetime

from neurons.form import HtmlForm, PasswordWidget, Tab
from neurons.form.const import T_TEST
from neurons.form.form import Fieldset
from spyne import Application, NullServer, Unicode, ServiceBase, rpc, Decimal, \
    Boolean, Date, Time, DateTime, Integer, ComplexModel, Array, Double
from lxml import etree
from spyne.util.test import show

logging.basicConfig(level=logging.DEBUG)


def _strip_ns(par):
    par.tag = par.tag.split('}', 1)[-1]
    if len(par.nsmap) > 0:
        par2 = etree.Element(par.tag, par.attrib)
        par2.text = par.text
        par2.tail = par.tail
        par2.extend(par.getchildren())

        par.getparent().insert(par.getparent().index(par), par2)
        par.getparent().remove(par)
        par = par2

    for elt in par:
        elt.tag = elt.tag.split('}', 1)[-1]
        if len(elt.nsmap) > 0:
            elt2 = etree.Element(elt.tag, elt.attrib)
            elt2.text = elt.text
            elt2.tail = elt.tail
            elt2.extend(elt.getchildren())

            elt.getparent().insert(elt.getparent().index(elt), elt2)
            elt.getparent().remove(elt)
            elt = elt2

        _strip_ns(elt)

    return par


def _test_type(cls, inst):
    from spyne.util import appreg; appreg._applications.clear()

    class SomeService(ServiceBase):
        @rpc(_returns=cls, _body_style='bare')
        def some_call(ctx):
            return inst

    prot = HtmlForm(cloth=T_TEST)
    app = Application([SomeService], 'some_ns', out_protocol=prot)

    null = NullServer(app, ostr=True)

    elt = etree.fromstring(''.join(null.service.some_call()))
    show(elt, stdout=False)
    elt = elt.xpath('//*[@spyne]')[0][0] # get the form tag inside the body tag.
    elt = _strip_ns(elt) # get rid of namespaces to simplify xpaths in tests

    print(etree.tostring(elt, pretty_print=True))

    return elt


def _test_type_no_root_cloth(cls, inst):
    from spyne.util import appreg; appreg._applications.clear()

    class SomeService(ServiceBase):
        @rpc(_returns=cls, _body_style='bare')
        def some_call(ctx):
            return inst

    prot = HtmlForm()
    app = Application([SomeService], 'some_ns', out_protocol=prot)

    null = NullServer(app, ostr=True)
    elt = etree.fromstring(''.join(null.service.some_call()))
    show(elt)

    return elt


class TestFormPrimitive(unittest.TestCase):
    def test_unicode(self):
        v = 'foo'
        elt = _test_type(Unicode, v).xpath('input')[0]
        assert elt.attrib['type'] == 'text'
        assert elt.attrib['name'] == 'string'
        assert elt.attrib['value'] == v

    def test_unicode_password(self):
        elt = _test_type(Unicode(prot=PasswordWidget()), None).xpath('input')[0]
        assert elt.attrib['type'] == 'password'

    def test_decimal(self):
        elt = _test_type(Decimal, D('0.1')).xpath('input')[0]
        assert elt.attrib['type'] == 'number'
        assert elt.attrib['step'] == 'any'

    # FIXME: enable this after fixing the relevant Spyne bug
    def _test_decimal_step(self):
        elt = _test_type(Decimal(fraction_digits=4), D('0.1')).xpath('input')[0]
        assert elt.attrib['step'] == '0.0001'

    def test_boolean_true(self):
        elt = _test_type(Boolean, True).xpath('input')[0]
        assert 'checked' in elt.attrib

    def test_boolean_false(self):
        elt = _test_type(Boolean, False).xpath('input')[0]
        assert not ('checked' in elt.attrib)

    def test_date(self):
        elt = _test_type(Date, date(2013, 12, 11)).xpath('input')[0]
        assert elt.attrib['value'] == '2013-12-11'
        # FIXME: Need to find a way to test the generated js

    def test_time(self):
        elt = _test_type(Time, time(10, 9, 8)).xpath('input')[0]
        assert elt.attrib['value'] == '10:09:08'
        # FIXME: Need to find a way to test the generated js

    def test_datetime(self):
        v = datetime(2013, 12, 11, 10, 9, 8)
        script = _test_type(DateTime, v).xpath('script/text()')[0]
        assert v.isoformat() in script
        # FIXME: Need to find a better way to test the generated js

    def test_integer(self):
        elt = _test_type(Integer, 42).xpath('input')[0]
        assert elt.attrib['value'] == '42'

    def test_integer_none(self):
        elt = _test_type(Integer, None).xpath('input')[0]
        assert not 'value' in elt.attrib


class TestFormComplex(unittest.TestCase):
    # all complex objects serialize to forms with fieldsets. that's why we
    # always run xpaths on elt[0] i.e. inside the fieldset where the data we're
    # after is, instead of running longer xpath queries.

    def test_simple(self):
        class SomeObject(ComplexModel):
            _type_info = [
                ('i', Integer),
                ('s', Unicode),
            ]

        v = SomeObject(i=42, s="Arthur")
        elt = _test_type(SomeObject, v)
        assert elt[0].xpath('input/@value') == ['42', 'Arthur']
        assert elt[0].xpath('input/@name') == ['i', 's']

    def test_nested(self):
        class InnerObject(ComplexModel):
            _type_info = [
                ('s', Unicode),
            ]
        class OuterObject(ComplexModel):
            _type_info = [
                ('i', InnerObject),
                ('d', Double),
            ]

        v = OuterObject(i=InnerObject(s="Arthur"), d=3.1415)
        elt = _test_type(OuterObject, v)

        # it's a bit risky doing this with doubles
        assert elt[0].xpath('input/@value') == ['3.1415']
        assert elt[0].xpath('input/@name') == ['d']
        assert elt[0].xpath('fieldset/input/@value') == ['Arthur']
        assert elt[0].xpath('fieldset/input/@name') == ['i.s']

    def test_fieldset(self):
        fset_one = Fieldset("One")
        fset_two = Fieldset("Two")
        class SomeObject(ComplexModel):
            _type_info = [
                ('i0', Integer),
                ('s0', Unicode),
                ('i1', Integer(fieldset=fset_one)),
                ('s1', Unicode(fieldset=fset_one)),
                ('i2', Integer(fieldset=fset_two)),
                ('s2', Unicode(fieldset=fset_two)),
            ]

        v = SomeObject(
            i0=42, s0="Arthur",
            i1=42, s1="Arthur",
            i2=42, s2="Arthur",
        )
        elt = _test_type(SomeObject, v)
        assert elt[0].xpath('input/@value') == ['42', 'Arthur']
        assert elt[0].xpath('input/@name') == ['i0', 's0']
        assert elt[0].xpath('fieldset/input/@value') == ['42', 'Arthur',
                                                         '42', 'Arthur']
        assert elt[0].xpath('fieldset/input/@name') == ['i1', 's1', 'i2', 's2']

    def test_tab(self):
        tab1 = Tab("One")
        tab2 = Tab("Two")
        class SomeObject(ComplexModel):
            _type_info = [
                ('i0', Integer),
                ('i1', Integer(tab=tab1)),
                ('i2', Integer(tab=tab2)),
            ]

        v = SomeObject(i0=14, i1=28, i2=56)
        elt = _test_type(SomeObject, v)
        assert elt[0].xpath('input/@value') == ['14']
        assert elt[0].xpath('input/@name') == ['i0']

        assert elt[0].xpath('div/ul/li/a/text()') == [tab1.legend, tab2.legend]
        assert elt[0].xpath('div/ul/li/a/@href') == ["#" + tab1.htmlid, "#" + tab2.htmlid]
        assert elt[0].xpath('div/div/@id') == [tab1.htmlid, tab2.htmlid]
        assert elt[0].xpath('div/div[@id]/input/@name') == ['i1', 'i2']
        assert elt[0].xpath('div/div[@id]/input/@value') == ['28', '56']

        # FIXME: properly test script tags
        assert elt[0].xpath('div/@id')[0] in elt[0].xpath('script/text()')[0]

    def test_simple_array(self):
        class SomeObject(ComplexModel):
            _type_info = [
                ('ints', Array(Integer)),
            ]

        v = SomeObject(ints=range(5))
        elt = _test_type(SomeObject, v)
        assert False


if __name__ == '__main__':
    unittest.main()
