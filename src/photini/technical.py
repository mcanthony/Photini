# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-15  Jim Easterbrook  jim@jim-easterbrook.me.uk
##
##  This program is free software: you can redistribute it and/or
##  modify it under the terms of the GNU General Public License as
##  published by the Free Software Foundation, either version 3 of the
##  License, or (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##  General Public License for more details.
##
##  You should have received a copy of the GNU General Public License
##  along with this program.  If not, see
##  <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from datetime import timedelta
import re

from .metadata import DateTime, LensSpec
from .pyqt import multiple, multiple_values, Qt, QtCore, QtGui, QtWidgets

class DropdownEdit(QtWidgets.QComboBox):
    new_value = QtCore.pyqtSignal()

    def __init__(self, *arg, **kw):
        super(DropdownEdit, self).__init__(*arg, **kw)
        self.addItem('', None)
        self.addItem(multiple(), None)
        self.currentIndexChanged.connect(self._new_value)

    @QtCore.pyqtSlot(int)
    def _new_value(self, index):
        if index >= 0:
            self.new_value.emit()

    def add_item(self, text, data=None):
        if data is None:
            data = text
        blocked = self.blockSignals(True)
        self.insertItem(self.count() - 2, str(text), str(data))
        self.blockSignals(blocked)

    def remove_item(self, data):
        blocked = self.blockSignals(True)
        self.removeItem(self.findData(data))
        self.blockSignals(blocked)

    def known_value(self, value):
        if not value:
            return True
        return self.findData(str(value)) >= 0

    def set_value(self, value):
        if not value:
            self.setCurrentIndex(self.count() - 2)
        else:
            self.setCurrentIndex(self.findData(str(value)))

    def get_value(self):
        return self.itemData(self.currentIndex())

    def set_multiple(self):
        self.setCurrentIndex(self.count() - 1)

    def is_multiple(self):
        return self.currentIndex() == self.count() - 1


class FloatEdit(QtWidgets.QLineEdit):
    def __init__(self, *arg, **kw):
        super(FloatEdit, self).__init__(*arg, **kw)
        self.multiple = multiple()
        self.setValidator(DoubleValidator())
        self._is_multiple = False

    def set_value(self, value):
        self._is_multiple = False
        if not value:
            self.clear()
            self.setPlaceholderText('')
        else:
            self.setText(str(value))

    def get_value(self):
        return self.text()

    def set_multiple(self):
        self._is_multiple = True
        self.setPlaceholderText(self.multiple)
        self.clear()

    def is_multiple(self):
        return self._is_multiple and not bool(self.get_value())


class DateTimeEdit(QtWidgets.QDateTimeEdit):
    new_precision = QtCore.pyqtSignal(int)

    def __init__(self, *arg, **kw):
        super(DateTimeEdit, self).__init__(*arg, **kw)
        self.datetime = None
        self.precision = -1
        # get size at full precision
        self.set_value(datetime=QtCore.QDateTime.currentDateTime(), precision=7)
        self.minimum_size = super(DateTimeEdit, self).sizeHint()
        # clear display
        self.set_value(precision=0)

    def sizeHint(self):
        return self.minimum_size

    def focusInEvent(self, event):
        if self.precision < 1:
            self.set_value(precision=1)
        elif self.dateTime() == self.minimumDateTime():
            self.setDateTime(self.datetime)
        super(DateTimeEdit, self).focusInEvent(event)

    def set_value(self, datetime=None, text=None, precision=None):
        new_datetime = datetime is not None and datetime != self.datetime
        if new_datetime:
            self.datetime = datetime
        new_precision = precision is not None and precision != self.precision
        if new_precision:
            self.precision = precision
            if self.precision == 0:
                text = ' '
            else:
                self.setDisplayFormat(
                    ''.join(('yyyy', '-MM', '-dd',
                             ' hh', ':mm', ':ss', '.zzz')[:self.precision]))
            self.new_precision.emit(self.precision)
        if text is not None:
            self.setSpecialValueText(text)
            self.setDateTime(self.minimumDateTime())
        elif self.precision != 0 and (new_datetime or new_precision):
            self.setDateTime(self.datetime)


class TimeZoneWidget(QtWidgets.QSpinBox):
    def __init__(self, *arg, **kw):
        super(TimeZoneWidget, self).__init__(*arg, **kw)
        self.setRange(45 - (15 * 60), 15 * 60)
        self.setSingleStep(15)
        self.setWrapping(True)
        self.setSpecialValueText(' ')

    def validate(self, text, pos):
        if re.match('[+-]?\d{1,2}(:\d{0,2})?$', text):
            return QtGui.QValidator.Acceptable, text, pos
        if re.match('[+-]?$', text):
            return QtGui.QValidator.Intermediate, text, pos
        return QtGui.QValidator.Invalid, text, pos

    def valueFromText(self, text):
        hours, sep, minutes = text.partition(':')
        hours = int(hours)
        if minutes:
            minutes = int(15.0 * round(float(minutes) / 15.0))
            if hours < 0:
                minutes = -minutes
        else:
            minutes = 0
        return (hours * 60) + minutes

    def textFromValue(self, value):
        if value < 0:
            sign = '-'
            value = -value
        else:
            sign = '+'
        return '{}{:02d}:{:02d}'.format(sign, value // 60, value % 60)

    def set_value(self, value):
        if value is None:
            self.setValue(self.minimum())
        else:
            self.setValue(value)


class Slider(QtWidgets.QSlider):
    editing_finished = QtCore.pyqtSignal()

    def focusOutEvent(self, event):
        self.editing_finished.emit()
        super(Slider, self).focusOutEvent(event)


class DateAndTimeWidget(QtWidgets.QGridLayout):
    new_value = QtCore.pyqtSignal(object)

    def __init__(self, *arg, **kw):
        super(DateAndTimeWidget, self).__init__(*arg, **kw)
        self.setContentsMargins(0, 0, 0, 0)
        self.setColumnStretch(3, 1)
        self.multiple = multiple_values()
        self._is_multiple = False
        self._enabled = True
        # date & time
        self.datetime = DateTimeEdit()
        self.datetime.setCalendarPopup(True)
        self.addWidget(self.datetime, 0, 0, 1, 2)
        # time zone
        self.time_zone = TimeZoneWidget()
        self.addWidget(self.time_zone, 0, 2)
        # precision
        self.addWidget(QtWidgets.QLabel(self.tr('Precision:')), 1, 0)
        self.precision = Slider(Qt.Horizontal)
        self.precision.setRange(0, 7)
        self.precision.setPageStep(1)
        self.addWidget(self.precision, 1, 1)
        # connections
        self.datetime.new_precision.connect(self.precision.setValue)
        self.datetime.editingFinished.connect(self.new_datetime)
        self.time_zone.editingFinished.connect(self.new_time_zone)
        self.precision.valueChanged.connect(self.set_precision)
        self.precision.editing_finished.connect(self.new_precision)

    @QtCore.pyqtSlot(int)
    def set_precision(self, precision):
        self.datetime.set_value(precision=precision)

    def get_value(self):
        if self._is_multiple:
            return None
        precision = self.datetime.precision
        if precision <= 0:
            return None
        tz_offset = self.time_zone.value()
        if tz_offset == self.time_zone.minimum():
            # special value - no time zone
            tz_offset = None
        return DateTime(self.datetime.datetime, precision, tz_offset)

    def set_value(self, value):
        blocked = self.precision.blockSignals(True)
        self._is_multiple = False
        if value is None:
            self.datetime.set_value(precision=0)
        else:
            self.datetime.set_value(
                datetime=value.value['datetime'], precision=value.value['precision'])
        if not value or value.value['precision'] <= 3:
            self.time_zone.set_value(None)
        else:
            self.time_zone.set_value(value.value['tz_offset'])
        self.time_zone.setEnabled(self._enabled)
        self.precision.blockSignals(blocked)

    def set_multiple(self):
        blocked = self.precision.blockSignals(True)
        self._is_multiple = True
        self.datetime.set_value(text=self.multiple, precision=7)
        self.time_zone.set_value(None)
        self.time_zone.setEnabled(False)
        self.precision.blockSignals(blocked)

    def set_enabled(self, enabled):
        self._enabled = enabled
        self.datetime.setEnabled(enabled)
        self.precision.setEnabled(enabled)

    @QtCore.pyqtSlot()
    def new_precision(self):
        self.new_value.emit(self.get_value())

    @QtCore.pyqtSlot()
    def new_datetime(self):
        self._is_multiple = False
        self.datetime.set_value(datetime=self.datetime.dateTime().toPyDateTime())
        self.new_value.emit(self.get_value())

    @QtCore.pyqtSlot()
    def new_time_zone(self):
        self.new_value.emit(self.get_value())


class SquareButton(QtWidgets.QPushButton):
    def sizeHint(self):
        size = super(SquareButton, self).sizeHint()
        size.setWidth(size.height())
        return size


class OffsetWidget(QtWidgets.QWidget):
    apply_offset = QtCore.pyqtSignal(timedelta)

    def __init__(self, *arg, **kw):
        super(OffsetWidget, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # offset value
        self.offset = QtWidgets.QTimeEdit()
        self.offset.setDisplayFormat("'h:'hh 'm:'mm 's:'ss")
        self.layout().addWidget(self.offset)
        # add offset button
        add_button = SquareButton(' + ')
        add_button.clicked.connect(self.add)
        self.layout().addWidget(add_button)
        # subtract offset button
        sub_button = SquareButton(' - ')
        sub_button.clicked.connect(self.sub)
        self.layout().addWidget(sub_button)

    @QtCore.pyqtSlot()
    def add(self):
        value = self.offset.time()
        offset = timedelta(
            hours=value.hour(), minutes=value.minute(), seconds=value.second())
        self.apply_offset.emit(offset)

    @QtCore.pyqtSlot()
    def sub(self):
        value = self.offset.time()
        offset = timedelta(
            hours=value.hour(), minutes=value.minute(), seconds=value.second())
        self.apply_offset.emit(-offset)


class DoubleValidator(QtGui.QDoubleValidator):
    def validate(self, input_, pos):
        # accept empty string as valid, to allow metadata to be cleared
        if input_ == '':
            return QtGui.QValidator.Acceptable, input_, pos
        return super(DoubleValidator, self).validate(input_, pos)


class LensData(object):
    def __init__(self, config_store):
        self.config_store = config_store
        self.lenses = eval(self.config_store.get('technical', 'lenses', '[]'))
        self.lenses.sort()

    def delete_model(self, model):
        if model not in self.lenses:
            return
        self.config_store.remove_section('lens ' + model)
        self.lenses.remove(model)
        self.config_store.set('technical', 'lenses', repr(self.lenses))

    def save_to_image(self, model, image):
        image.metadata.lens_model = model
        if not model:
            for item in ('lens_make', 'lens_serial', 'lens_spec'):
                setattr(image.metadata, item, None)
            return
        section = 'lens ' + model
        for item in ('lens_make', 'lens_serial', 'lens_spec'):
            value = self.config_store.get(section, item) or None
            setattr(image.metadata, item, value)

    def load_from_image(self, model, image):
        model = str(model)
        section = 'lens ' + model
        for item in ('lens_make', 'lens_serial', 'lens_spec'):
            value = getattr(image.metadata, item)
            if value:
                self.config_store.set(section, item, str(value))
        self.lenses.append(model)
        self.lenses.sort()
        self.config_store.set('technical', 'lenses', repr(self.lenses))

    def load_from_dialog(self, dialog):
        model = dialog.lens_model.text()
        if not model:
            return None
        min_fl = dialog.lens_spec['min_fl'].text()
        if not min_fl:
            return None
        max_fl = dialog.lens_spec['max_fl'].text() or min_fl
        min_fl_fn = dialog.lens_spec['min_fl_fn'].text() or '0'
        max_fl_fn = dialog.lens_spec['max_fl_fn'].text() or min_fl_fn
        lens_spec = LensSpec((min_fl, max_fl, min_fl_fn, max_fl_fn))
        section = 'lens ' + model
        self.config_store.set(section, 'lens_make', dialog.lens_make.text())
        self.config_store.set(section, 'lens_serial', dialog.lens_serial.text())
        self.config_store.set(section, 'lens_spec', str(lens_spec))
        self.lenses.append(model)
        self.lenses.sort()
        self.config_store.set('technical', 'lenses', repr(self.lenses))
        return model


class NewLensDialog(QtWidgets.QDialog):
    def __init__(self, *arg, **kw):
        super(NewLensDialog, self).__init__(*arg, **kw)
        self.setWindowTitle(self.tr('Photini: define lens'))
        self.setLayout(QtWidgets.QVBoxLayout())
        # main dialog area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.layout().addWidget(scroll_area)
        panel = QtWidgets.QWidget()
        panel.setLayout(QtWidgets.QFormLayout())
        # ok & cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout().addWidget(button_box)
        # model
        self.lens_model = QtWidgets.QLineEdit()
        panel.layout().addRow(self.tr('Model name'), self.lens_model)
        # maker
        self.lens_make = QtWidgets.QLineEdit()
        panel.layout().addRow(self.tr("Maker's name"), self.lens_make)
        # serial number
        self.lens_serial = QtWidgets.QLineEdit()
        panel.layout().addRow(self.tr('Serial number'), self.lens_serial)
        ## spec has four items
        self.lens_spec = {}
        # min focal length
        self.lens_spec['min_fl'] = QtWidgets.QLineEdit()
        self.lens_spec['min_fl'].setValidator(QtGui.QDoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Minimum focal length (mm)'),
                              self.lens_spec['min_fl'])
        # min focal length aperture
        self.lens_spec['min_fl_fn'] = QtWidgets.QLineEdit()
        self.lens_spec['min_fl_fn'].setValidator(DoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Aperture at min. focal length f/'),
                              self.lens_spec['min_fl_fn'])
        # max focal length
        self.lens_spec['max_fl'] = QtWidgets.QLineEdit()
        self.lens_spec['max_fl'].setValidator(QtGui.QDoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Maximum focal length (mm)'),
                              self.lens_spec['max_fl'])
        # max focal length aperture
        self.lens_spec['max_fl_fn'] = QtWidgets.QLineEdit()
        self.lens_spec['max_fl_fn'].setValidator(DoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Aperture at max. focal length f/'),
                              self.lens_spec['max_fl_fn'])
        # add panel to scroll area after its size is known
        scroll_area.setWidget(panel)


class Technical(QtWidgets.QWidget):
    def __init__(self, config_store, image_list, *arg, **kw):
        super(Technical, self).__init__(*arg, **kw)
        self.config_store = config_store
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.widgets = {}
        self.date_widget = {}
        self.link_widget = {}
        # store lens data in another object
        self.lens_data = LensData(self.config_store)
        # date and time
        date_group = QtWidgets.QGroupBox(self.tr('Date and time'))
        date_group.setLayout(QtWidgets.QFormLayout())
        # taken
        self.date_widget['taken'] = DateAndTimeWidget()
        self.date_widget['taken'].new_value.connect(self.new_date_taken)
        date_group.layout().addRow(self.tr('Taken'), self.date_widget['taken'])
        # link taken & digitised
        self.link_widget['taken', 'digitised'] = QtWidgets.QCheckBox(
            self.tr("Link 'taken' and 'digitised'"))
        self.link_widget[
            'taken', 'digitised'].clicked.connect(self.new_link_digitised)
        date_group.layout().addRow('', self.link_widget['taken', 'digitised'])
        # digitised
        self.date_widget['digitised'] = DateAndTimeWidget()
        self.date_widget['digitised'].new_value.connect(self.new_date_digitised)
        date_group.layout().addRow(
            self.tr('Digitised'), self.date_widget['digitised'])
        # link digitised & modified
        self.link_widget['digitised', 'modified'] = QtWidgets.QCheckBox(
            self.tr("Link 'digitised' and 'modified'"))
        self.link_widget[
            'digitised', 'modified'].clicked.connect(self.new_link_modified)
        date_group.layout().addRow('', self.link_widget['digitised', 'modified'])
        # modified
        self.date_widget['modified'] = DateAndTimeWidget()
        self.date_widget['modified'].new_value.connect(self.new_date_modified)
        date_group.layout().addRow(
            self.tr('Modified'), self.date_widget['modified'])
        # offset
        self.offset_widget = OffsetWidget()
        self.offset_widget.apply_offset.connect(self.apply_offset)
        date_group.layout().addRow(self.tr('Adjust times'), self.offset_widget)
        self.layout().addWidget(date_group, 0, 0)
        # other
        other_group = QtWidgets.QGroupBox(self.tr('Other'))
        other_group.setLayout(QtWidgets.QFormLayout())
        # orientation
        self.widgets['orientation'] = DropdownEdit()
        self.widgets['orientation'].add_item(self.tr('normal'), 1)
        self.widgets['orientation'].add_item(self.tr('rotate -90'), 6)
        self.widgets['orientation'].add_item(self.tr('rotate +90'), 8)
        self.widgets['orientation'].add_item(self.tr('rotate 180'), 3)
        self.widgets['orientation'].add_item(self.tr('reflect left-right'), 2)
        self.widgets['orientation'].add_item(self.tr('reflect top-bottom'), 4)
        self.widgets['orientation'].add_item(self.tr('reflect tr-bl'), 5)
        self.widgets['orientation'].add_item(self.tr('reflect tl-br'), 7)
        self.widgets['orientation'].new_value.connect(self.new_orientation)
        other_group.layout().addRow(
            self.tr('Orientation'), self.widgets['orientation'])
        # lens model
        self.widgets['lens_model'] = DropdownEdit()
        self.widgets['lens_model'].setContextMenuPolicy(Qt.CustomContextMenu)
        self.widgets['lens_model'].add_item(
            self.tr('<define new lens>'), '<add lens>')
        for model in self.lens_data.lenses:
            self.widgets['lens_model'].add_item(model)
        self.widgets['lens_model'].new_value.connect(self.new_lens_model)
        self.widgets['lens_model'].customContextMenuRequested.connect(
            self.remove_lens_model)
        other_group.layout().addRow(
            self.tr('Lens model'), self.widgets['lens_model'])
        # link lens to aperture & focal length
        self.link_lens = QtWidgets.QCheckBox(
            self.tr("Link lens model to\nfocal length && aperture"))
        self.link_lens.setChecked(True)
        other_group.layout().addRow('', self.link_lens)
        # focal length
        self.widgets['focal_length'] = FloatEdit()
        self.widgets['focal_length'].validator().setBottom(0.1)
        self.widgets['focal_length'].setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.widgets['focal_length'].editingFinished.connect(self.new_focal_length)
        other_group.layout().addRow(
            self.tr('Focal length (mm)'), self.widgets['focal_length'])
        # aperture
        self.widgets['aperture'] = FloatEdit()
        self.widgets['aperture'].validator().setBottom(0.1)
        self.widgets['aperture'].setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.widgets['aperture'].editingFinished.connect(self.new_aperture)
        other_group.layout().addRow(
            self.tr('Aperture f/'), self.widgets['aperture'])
        self.layout().addWidget(other_group, 0, 1)
        self.layout().setColumnStretch(0, 1)
        self.layout().setColumnStretch(1, 1)
        # disable until an image is selected
        self.setEnabled(False)

    def refresh(self):
        pass

    def do_not_close(self):
        return False

    def shutdown(self):
        pass

    @QtCore.pyqtSlot(object)
    def new_date_taken(self, value):
        self._new_date_value('taken', value)
        if self.link_widget['taken', 'digitised'].isChecked():
            self.new_date_digitised(value)

    @QtCore.pyqtSlot(object)
    def new_date_digitised(self, value):
        self._new_date_value('digitised', value)
        if self.link_widget['digitised', 'modified'].isChecked():
            self.new_date_modified(value)

    @QtCore.pyqtSlot(object)
    def new_date_modified(self, value):
        self._new_date_value('modified', value)

    @QtCore.pyqtSlot(timedelta)
    def apply_offset(self, offset):
        for image in self.image_list.get_selected_images():
            date_taken = image.metadata.date_taken
            if not date_taken:
                continue
            date_taken.value['datetime'] += offset
            image.metadata.date_taken = date_taken
            if self.link_widget['taken', 'digitised'].isChecked():
                image.metadata.date_digitised = date_taken
                if self.link_widget['digitised', 'modified'].isChecked():
                    image.metadata.date_modified = date_taken
        self._update_datetime('taken')
        if self.link_widget['taken', 'digitised'].isChecked():
            self._update_datetime('digitised')
            if self.link_widget['digitised', 'modified'].isChecked():
                self._update_datetime('modified')

    @QtCore.pyqtSlot()
    def new_link_digitised(self):
        if self.link_widget['taken', 'digitised'].isChecked():
            self.date_widget['digitised'].set_enabled(False)
            self.new_date_digitised(
                self.date_widget['taken'].datetime.get_value())
        else:
            self.date_widget['digitised'].set_enabled(True)

    @QtCore.pyqtSlot()
    def new_link_modified(self):
        if self.link_widget['digitised', 'modified'].isChecked():
            self.date_widget['modified'].set_enabled(False)
            self.new_date_modified(
                self.date_widget['digitised'].datetime.get_value())
        else:
            self.date_widget['modified'].set_enabled(True)

    @QtCore.pyqtSlot()
    def new_orientation(self):
        if self.widgets['orientation'].is_multiple():
            self._update_orientation()
            return
        value = self.widgets['orientation'].get_value()
        if value is not None:
            value = int(value)
        for image in self.image_list.get_selected_images():
            image.metadata.orientation = value
            image.load_thumbnail()

    @QtCore.pyqtSlot(QtCore.QPoint)
    def remove_lens_model(self, pos):
        current_model = self.widgets['lens_model'].get_value()
        menu = QtWidgets.QMenu()
        for model in self.lens_data.lenses:
            if model == current_model:
                continue
            action = QtWidgets.QAction(
                self.tr('Remove lens "{}"').format(model), self)
            action.setData(model)
            menu.addAction(action)
        if menu.isEmpty():
            # no deletable lenses
            return
        action = menu.exec_(self.widgets['lens_model'].mapToGlobal(pos))
        if not action:
            return
        model = action.data()
        self.lens_data.delete_model(model)
        self.widgets['lens_model'].remove_item(model)

    @QtCore.pyqtSlot()
    def new_lens_model(self):
        if self.widgets['lens_model'].is_multiple():
            self._update_lens_model()
            return
        value = self.widgets['lens_model'].get_value()
        if value == '<add lens>':
            self._add_lens_model()
            self._update_lens_model()
            return
        for image in self.image_list.get_selected_images():
            self.lens_data.save_to_image(value, image)
        if not self.link_lens.isChecked():
            return
        for image in self.image_list.get_selected_images():
            spec = image.metadata.lens_spec
            if not spec:
                continue
            if not image.metadata.aperture:
                image.metadata.aperture = 0
            if not image.metadata.focal_length:
                image.metadata.focal_length = 0
            aperture = image.metadata.aperture.value
            focal_length = image.metadata.focal_length.value
            if focal_length <= spec.value['min_fl']:
                focal_length = spec.value['min_fl']
                aperture = max(aperture, spec.value['min_fl_fn'])
            elif focal_length >= spec.value['max_fl']:
                focal_length = spec.value['max_fl']
                aperture = max(aperture, spec.value['max_fl_fn'])
            else:
                aperture = max(aperture, min(spec.value['min_fl_fn'],
                                             spec.value['max_fl_fn']))
            image.metadata.aperture = aperture
            image.metadata.focal_length = focal_length
        self._update_aperture()
        self._update_focal_length()

    def _add_lens_model(self):
        dialog = NewLensDialog(self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        model = self.lens_data.load_from_dialog(dialog)
        if not model:
            return
        self.widgets['lens_model'].add_item(model)

    @QtCore.pyqtSlot()
    def new_aperture(self):
        if not self.widgets['aperture'].is_multiple():
            value = self.widgets['aperture'].get_value()
            for image in self.image_list.get_selected_images():
                image.metadata.aperture = value

    @QtCore.pyqtSlot()
    def new_focal_length(self):
        if not self.widgets['focal_length'].is_multiple():
            value = self.widgets['focal_length'].get_value()
            for image in self.image_list.get_selected_images():
                image.metadata.focal_length = value

    def _new_date_value(self, key, value):
        for image in self.image_list.get_selected_images():
            setattr(image.metadata, 'date_' + key, value)
        self._update_datetime(key)

    def _update_datetime(self, key):
        images = self.image_list.get_selected_images()
        if not images:
            return
        value = getattr(images[0].metadata, 'date_' + key)
        for image in images[1:]:
            new_value = getattr(image.metadata, 'date_' + key)
            if new_value != value:
                # multiple values
                self.date_widget[key].set_multiple()
                return
        self.date_widget[key].set_value(value)

    def _update_orientation(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        value = images[0].metadata.orientation
        for image in images[1:]:
            if image.metadata.orientation != value:
                # multiple values
                self.widgets['orientation'].set_multiple()
                return
        self.widgets['orientation'].set_value(value)

    def _update_lens_model(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        value = images[0].metadata.lens_model
        for image in images[1:]:
            if image.metadata.lens_model != value:
                # multiple values
                self.widgets['lens_model'].set_multiple()
                return
        if self.link_lens.isChecked():
            for image in images:
                spec = image.metadata.lens_spec
                if not spec:
                    continue
                focal_length = image.metadata.focal_length
                if focal_length and (
                        focal_length.value < spec.value['min_fl'] or
                        focal_length.value > spec.value['max_fl']):
                    self.link_lens.setChecked(False)
                    break
                aperture = image.metadata.aperture
                if aperture and aperture.value < min(spec.value['min_fl_fn'],
                                                     spec.value['max_fl_fn']):
                    self.link_lens.setChecked(False)
                    break
        if not self.widgets['lens_model'].known_value(value):
            # new lens
            self.lens_data.load_from_image(value, images[0])
            self.widgets['lens_model'].add_item(value)
        self.widgets['lens_model'].set_value(value)

    def _update_aperture(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        value = images[0].metadata.aperture
        for image in images[1:]:
            if image.metadata.aperture != value:
                self.widgets['aperture'].set_multiple()
                return
        self.widgets['aperture'].set_value(value)

    def _update_focal_length(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        value = images[0].metadata.focal_length
        for image in images[1:]:
            if image.metadata.focal_length != value:
                self.widgets['focal_length'].set_multiple()
                return
        self.widgets['focal_length'].set_value(value)

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        if not selection:
            self.setEnabled(False)
            for key in self.date_widget:
                self.date_widget[key].set_value(None)
            for key in self.widgets:
                self.widgets[key].set_value(None)
            return
        for key in self.date_widget:
            self._update_datetime(key)
        for master, slave in self.link_widget:
            if (self.date_widget[slave].get_value() ==
                                self.date_widget[master].get_value() and
                    self.date_widget[slave].get_value() ==
                                self.date_widget[master].get_value()):
                self.date_widget[slave].set_enabled(False)
                self.link_widget[master, slave].setChecked(True)
            else:
                self.date_widget[slave].set_enabled(True)
                self.link_widget[master, slave].setChecked(False)
        self._update_orientation()
        self._update_lens_model()
        self._update_aperture()
        self._update_focal_length()
        self.setEnabled(True)
