import os
import sys
from dataclasses import dataclass, field
from typing import List

from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QRadioButton,
)

import requests

from support import (
    get_organization,
    get_place_map,
    get_place_toponym,
    lonlat_distance,
)

# для экранов с высоким разрешением
if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
    QtWidgets.QApplication.setAttribute(
        QtCore.Qt.AA_EnableHighDpiScaling, True
    )
if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)


# текущее состояние карты
@dataclass
class MapsData:
    spn: float = 0.003
    coords: List[float] = field(default_factory=list)
    display: str = 'map'
    pt: str = ''
    postal_code: str = ''
    address: str = ''


class MainWindow(QMainWindow):
    def __init__(self):
        super(QMainWindow, self).__init__()
        self.setupUI()

    def setupUI(self) -> None:
        self.setupData()
        uic.loadUi('UI/MainWindow.ui', self)
        self.setWindowTitle('Best Maps App')
        self.map_type_group.buttonClicked.connect(self.chooseMapType)
        self.search_place_button.clicked.connect(self.searchPlace)
        self.reset_search_button.clicked.connect(self.resetSearchResult)
        self.postal_code_checkbox.stateChanged.connect(self.resetPostalCode)
        self.getPicture()

    def setupData(self) -> None:
        """устанавливаем начальные координаты"""
        self.data = MapsData()
        self.data.coords = [30.312363709126018, 59.94157564755226]
        self.map_type_choices = {
            'Схема': 'map',
            'Спутник': 'sat',
            'Гибрид': 'sat,skl',
        }

    def getPicture(self) -> None:
        """получаем картинку запросом"""
        response = get_place_map(self.data)
        if response:
            self.setPicture(response)
        else:
            self.showMessage(
                'reqerror',
                f'Ошибка запроса: {response.status_code}. '
                f'Причина: {response.reason}, {response.request.url}',
            )

    def setPicture(self, response: requests.Response) -> None:
        """ставим изображение из ответа сервера"""
        with open('image.png', 'wb') as file:
            file.write(response.content)
        pixmap = QPixmap('image.png')
        self.picture.setPixmap(pixmap)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """обработка клавиш"""
        key = event.key()

        if key == Qt.Key.Key_PageUp:
            if self.data.spn != 89:
                self.data.spn = min(self.data.spn * 2, 89)
                self.getPicture()

        elif key == Qt.Key.Key_PageDown:
            if self.data.spn != 0.002:
                self.data.spn = max(self.data.spn / 2, 0.002)
                self.getPicture()

        elif key == Qt.Key.Key_W:
            self.data.coords[1] += self.data.spn
            if self.data.coords[1] > 85:
                self.data.coords[1] = 85
            else:
                self.getPicture()

        elif key == Qt.Key.Key_S:
            self.data.coords[1] -= self.data.spn
            if self.data.coords[1] < 1:
                self.data.coords[1] = min(self.data.spn, 1)
            else:
                self.getPicture()

        elif key == Qt.Key.Key_D:
            self.data.coords[0] += self.data.spn
            if self.data.coords[0] > 179:
                self.data.coords[0] = 179
            else:
                self.getPicture()

        elif key == Qt.Key.Key_A:
            self.data.coords[0] -= self.data.spn
            if self.data.coords[0] < 1:
                self.data.coords[0] = min(self.data.spn, 1)
            else:
                self.getPicture()

    def showMessage(self, action: str, text: str) -> None:
        """сообщение пользователю"""
        if action == 'reqerror':
            QMessageBox.critical(self, 'Ошибка запроса', text, QMessageBox.Ok)

    def chooseMapType(self, button: QRadioButton) -> None:
        """смена типа карты"""
        self.data.display = self.map_type_choices[button.text()]
        self.getPicture()

    def searchPlace(self, coords: str = '') -> None:
        """поиск места из ввода пользователя"""
        place = self.search_place_input.toPlainText().strip()
        if coords:
            toponym = get_place_toponym(coords=coords)
        elif place:
            toponym = get_place_toponym(place_name=place)
        else:
            return

        if toponym:
            toponym = toponym.json()['response']['GeoObjectCollection'][
                'featureMember'
            ][0]['GeoObject']
            if coords:
                self.setPlace(toponym, coords)
            else:
                self.setPlace(toponym)
        else:
            self.showMessage(
                'reqerror',
                f'Ошибка запроса: {toponym.status_code}.'
                f' Причина: {toponym.reason}',
            )

    def setPlace(self, toponym: dict, coords: str = '') -> None:
        """ставим метку на карте и позиционируем ее"""
        toponym_address = toponym['metaDataProperty']['GeocoderMetaData'][
            'text'
        ]
        toponym_coords = toponym['Point']['pos']

        if not coords:
            self.data.coords = list(map(float, toponym_coords.split()))
            self.data.spn = 0.003
            self.data.pt = (
                ','.join(list(map(str, toponym_coords.split()))) + ',pm2rdm'
            )
        else:
            self.data.pt = coords + ',pm2rdm'
        self.data.address = toponym_address

        self.getPicture()
        self.getPostalCode(toponym)
        self.resetPostalCode()

    def getPostalCode(self, toponym: dict) -> None:
        """получаем почтовый код"""
        try:
            self.data.postal_code = toponym['metaDataProperty'][
                'GeocoderMetaData'
            ]
            ['Address']['postal_code']
        except Exception:
            self.data.postal_code = ''

    def resetSearchResult(self) -> None:
        """удаляем метку"""
        self.data.pt = ''
        self.data.postal_code = ''
        self.data.address = ''
        self.search_address_edit.setPlainText('')
        self.getPicture()

    def resetPostalCode(self) -> None:
        """реагируем на изменение чекбокса почтового кода"""
        if self.postal_code_checkbox.isChecked() and self.data.postal_code:
            self.search_address_edit.setPlainText(
                self.data.address + ' (' + self.data.postal_code + ')'
            )
        else:
            self.search_address_edit.setPlainText(self.data.address)

    def mouseToCoords(self, mouse_pos: tuple) -> tuple:
        """получаем координаты точки из клика по карте"""
        x, y = mouse_pos[0] - 10, mouse_pos[1] - 10
        if 0 <= x <= 600 and 0 <= y <= 450:
            coord_1 = (
                self.data.coords[0]
                - self.data.spn / 2
                + self.data.spn / 600 * x
            )
            coord_2 = (
                self.data.coords[1]
                - self.data.spn / 2
                + self.data.spn / 450 * y
            )
            return (coord_1, coord_2)
        else:
            return (False, False)

    def searchPlaceClick(self, mouse_pos: tuple) -> None:
        """поиск места по клику ЛКМ"""
        coord_1, coord_2 = self.mouseToCoords(mouse_pos)
        if coord_1:
            self.searchPlace(coords=f'{coord_1},{coord_2}')

    def searchOrganization(self, mouse_pos: tuple) -> None:
        """поиск организации по клику ПКМ"""
        coord_1, coord_2 = self.mouseToCoords(mouse_pos)
        if coord_1:
            response = get_organization(f'{coord_1},{coord_2}')
            if response:
                response_json = response.json()
                try:
                    organization = response_json['features'][0]
                    # название организации
                    org_name = organization['properties']['CompanyMetaData'][
                        'name'
                    ]
                    # адрес организации
                    org_address = organization['properties'][
                        'CompanyMetaData'
                    ]['address']
                    # координаты
                    coords = organization['geometry']['coordinates']

                    # расстояние не более 50м
                    if lonlat_distance(self.data.coords, coords) <= 50:
                        self.data.pt = (
                            ','.join(list(map(str, coords))) + ',pm2rdm'
                        )
                        self.data.postal_code = ''
                        self.data.address = org_name + '\n' + org_address

                        self.getPicture()
                        self.resetPostalCode()
                except Exception:
                    return
            else:
                self.showMessage(
                    'reqerror',
                    f'Ошибка запроса: {response.status_code}. '
                    f'Причина: {response.reason}, {response.request.url}',
                )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """обрабатываем нажатия мыши"""
        if event.button() == Qt.LeftButton:
            self.searchPlaceClick((event.x(), event.y()))
        else:
            self.searchOrganization((event.x(), event.y()))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """удаляем картинку при закрытии приложения"""
        os.remove('image.png')


# ловим ошибки от PyQT
def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    sys.excepthook = except_hook
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
