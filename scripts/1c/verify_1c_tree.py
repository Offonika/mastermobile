#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

MANIFEST: dict[str, dict[str, object]] = {
    "config_dump_txt/Документ.ВозвратТоваровОтПокупателя.Макет.Накладная.Макет.mxl": {
        "size": 6466,
        "sha256": "004dfab2e6b66e8bdaf032c6b012fcd8e58617b3e369d7aaed0e5ed69c38aa5f"
    },
    "config_dump_txt/Документ.ВозвратТоваровОтПокупателя.Макет.НакладнаяКомментарии.Макет.mxl": {
        "size": 6975,
        "sha256": "84e8804d5cc23b69dc55baea9a7f5f13495f6122067b2c0e6567bdbb8ec55035"
    },
    "config_dump_txt/Документ.ВозвратТоваровОтПокупателя.МодульОбъекта.txt": {
        "size": 268099,
        "sha256": "6ef425889ac251a5ba992209a7252c53e932dff26b73dd3bd6f245bf8af12a59"
    },
    "config_dump_txt/Документ.ВозвратТоваровОтПокупателя.Форма.ФормаВыбора.Форма.Модуль.txt": {
        "size": 1672,
        "sha256": "256984cb62bc879971463ff0ff7567042dc95d8b0fb2bc676f246c2293c77ae8"
    },
    "config_dump_txt/Документ.ВозвратТоваровОтПокупателя.Форма.ФормаДокумента.Форма.Модуль.txt": {
        "size": 233207,
        "sha256": "0be8555a59ceaed9ab32630f3e9424c39442854c40a9ba98eb20e8397785ea45"
    },
    "config_dump_txt/Документ.ВозвратТоваровОтПокупателя.Форма.ФормаСписка.Форма.Модуль.txt": {
        "size": 3653,
        "sha256": "e0b8f2af98fec7079c99a9fadac790ec62f3b8b9d8aeef97826d54f6d0cc11c5"
    },
    "config_dump_txt/Документ.ПеремещениеТоваров.Макет.Накладная.Макет.mxl": {
        "size": 6539,
        "sha256": "d4f5df035ef832f654ed4c0f1cca120b9d4be34e413afab88ba99f90b4fae933"
    },
    "config_dump_txt/Документ.ПеремещениеТоваров.МодульОбъекта.txt": {
        "size": 244713,
        "sha256": "8268a8228beac3ae01eb1092b8ab804966d6cfd36ff8d69a18f5fbf08f7d1b21"
    },
    "config_dump_txt/Документ.ПеремещениеТоваров.Форма.ФормаВыбора.Форма.Модуль.txt": {
        "size": 1672,
        "sha256": "256984cb62bc879971463ff0ff7567042dc95d8b0fb2bc676f246c2293c77ae8"
    },
    "config_dump_txt/Документ.ПеремещениеТоваров.Форма.ФормаДляПроверки.Форма.Модуль.txt": {
        "size": 76279,
        "sha256": "2f042501235c10d3b85ebdbb497f1e3ca42a3bbfd186735112dbdbcaa5033d3d"
    },
    "config_dump_txt/Документ.ПеремещениеТоваров.Форма.ФормаДокумента.Форма.Модуль.txt": {
        "size": 157274,
        "sha256": "5050dc6831978f2fc7bd3461cb0cf043328cf67ee4f0616d7836f03ef6c0b8a0"
    },
    "config_dump_txt/Документ.ПеремещениеТоваров.Форма.ФормаПроверки.Форма.Модуль.txt": {
        "size": 111216,
        "sha256": "311c45a03aba507f09816094c73279c0364c25146df6847ead7cd55922d9c541"
    },
    "config_dump_txt/Документ.ПеремещениеТоваров.Форма.ФормаСписка.Форма.Модуль.txt": {
        "size": 10474,
        "sha256": "7447344f1f4203ad18be1420c05b9f125a3e9e1713e6a5741b33a4575a7c0e16"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Макет.Акт.Макет.mxl": {
        "size": 7862,
        "sha256": "df6f5cee55a3139051a9a80946d152f5fb7f14bdebac57254b3dbb21a1e84f27"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Макет.МакетСБ1.Макет.mxl": {
        "size": 2600,
        "sha256": "8bffbf88a5b1e8bb4ac2bc48957d26c4c5e294774dad81758f2c0cbfaf6f8d52"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Макет.МакетСБ2.Макет.mxl": {
        "size": 2599,
        "sha256": "8cfa0f9e576c058960341b5ca4488b90b275b1fdae268b1776ca6e0ba7a09d16"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Макет.Накладная.Макет.mxl": {
        "size": 24952,
        "sha256": "d71966658c494943bfacf0976aa5687998b2c95e24f5b13ab1b5fe512e8f7016"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Макет.Накладная1.Макет.mxl": {
        "size": 24462,
        "sha256": "62e677ef4166b44a881d0f58f341664f97fec04426721f022859d706a2389b9a"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Макет.Накладная3.Макет.mxl": {
        "size": 24462,
        "sha256": "62e677ef4166b44a881d0f58f341664f97fec04426721f022859d706a2389b9a"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Макет.НакладнаяДляИПГулиев.Макет.mxl": {
        "size": 24867,
        "sha256": "bc0ffda0be88a53b8cd9fdaa0c63d3e6517dbed466d7b118f11adc18e5eeba24"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Макет.НакладнаяДляИПСоловьев.Макет.mxl": {
        "size": 24877,
        "sha256": "c3859957c985b0639c7019e25db1dc9b4e74076b47ebd0be0bc2f38f210bc2ad"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Макет.НакладнаяДляМосквы.Макет.mxl": {
        "size": 24766,
        "sha256": "5b74058dd08df7b9fb60b976e9353b7a7581d342d4c3156e49d2e578395ec0da"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.МодульОбъекта.txt": {
        "size": 507144,
        "sha256": "9a0edbf6b1ffab631f196d8f1f7bf2370b300a292dff47fed3f94db16f5635a9"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Форма.ФормаВыбора.Форма.Модуль.txt": {
        "size": 2281,
        "sha256": "14d6b1552963d279651cea5f90cfdfe8800a023a5ddfc87122156c6ed9df3deb"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Форма.ФормаДокумента.Форма.Модуль.txt": {
        "size": 317552,
        "sha256": "5d253135020eacdd45f1da0a368ae226267df436cfe65a2320a9d2f19e227a35"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Форма.ФормаОтбораЗаказов.Форма.Модуль.txt": {
        "size": 225000,
        "sha256": "a1af5bc9d09c855a91375deea4c22955438e6dfc5e15bf16f0fa475b15d2f131"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Форма.ФормаПроверки.Форма.Модуль.txt": {
        "size": 116631,
        "sha256": "a2baaeed071568e04531820d89e5208a251a611b25e2b49db269c58e0b6bdae8"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Форма.ФормаСписка.Форма.Модуль.txt": {
        "size": 5530,
        "sha256": "ddcdb0714c5b13a4f493a64bfae266b3587599d428d56ac55e46815022ac4a1c"
    },
    "config_dump_txt/Документ.РеализацияТоваровУслуг.Форма.ФормаФормированияПакетаДокументов.Форма.Модуль.txt": {
        "size": 51748,
        "sha256": "b5c6a80cb9cc5c427a421c2afaef9b51f3f7b7b34659b2aaeb2d2d6bd1797fbf"
    },
    "config_dump_txt/Обработка.eCommerce_ПросмотрТоваровПрайсЛистов.Форма.Товары.Форма.Модуль.txt": {
        "size": 8239,
        "sha256": "d191c494a2c7498702e63d1e280ec9bca5dbbca0ba3de8013527bf2ce77c1a1f"
    },
    "config_dump_txt/ОбщийМодуль.ОбщегоНазначения.Модуль.txt": {
        "size": 252851,
        "sha256": "0d7baa17bc71b0dc090f13ad8ced1df36b0c613a5d0406325748e0ae16376040"
    },
    "config_dump_txt/Отчет.ТоварыВРезервеНаСкладах.МодульОбъекта.txt": {
        "size": 22398,
        "sha256": "0cbc92b834433019549bbae799d1fea8775c9cc30127ac81d84a85f429ec327b"
    },
    "config_dump_txt/Отчет.ТоварыВРезервеНаСкладах.Форма.Форма.Форма.Модуль.txt": {
        "size": 9921,
        "sha256": "adece3a2ac7c0a7b14443dfa4ee4e5b9f6dd2132eebea0057acb8850c092b4cf"
    },
    "config_dump_txt/РегистрНакопления.ТоварыВНТТ.МодульНабораЗаписей.txt": {
        "size": 14550,
        "sha256": "d61be7f1b18099e63bb1b6418e1ecd55f8027ddadfab789dc7492329e5b65d22"
    },
    "config_dump_txt/РегистрНакопления.ТоварыВРезервеНаСкладах.МодульНабораЗаписей.txt": {
        "size": 133553,
        "sha256": "7ba8fee191ab3a817c0cdae5aaf034f974d28363192924ce3e6bf5dba3b63122"
    },
    "config_dump_txt/РегистрНакопления.ТоварыВРознице.МодульНабораЗаписей.txt": {
        "size": 169847,
        "sha256": "cf62a4867f84926e0b9c5e8a587cb943c92ff538cf0d285efc2152e878a3bee8"
    },
    "config_dump_txt/РегистрНакопления.ТоварыКПередачеОрганизаций.МодульНабораЗаписей.txt": {
        "size": 34956,
        "sha256": "b1796f9f0d622f36fc570c17e78b260b022c935ff6b60f2ee0aaacfaf3e680c8"
    },
    "config_dump_txt/РегистрНакопления.ТоварыКПередачеСоСкладов.МодульНабораЗаписей.txt": {
        "size": 78041,
        "sha256": "3cf69094234d94cf7d73e968b8819c2297edcf4c7ab46f80f56f65e4ccf92fb9"
    },
    "config_dump_txt/РегистрНакопления.ТоварыКПеремещениюВНТТ.МодульНабораЗаписей.txt": {
        "size": 14302,
        "sha256": "29734b35b1845394f982bbbbc498b5d1d0989e992ac218fdb5c912f2fcac24d8"
    },
    "config_dump_txt/РегистрНакопления.ТоварыКПолучениюНаСклады.МодульНабораЗаписей.txt": {
        "size": 22041,
        "sha256": "fe5d9050c6600bc480cb9a9eed9c546a893d12e2e227479b90c76e957fb37c45"
    },
    "config_dump_txt/РегистрНакопления.ТоварыНаСкладах.МодульНабораЗаписей.txt": {
        "size": 171527,
        "sha256": "833935f7878af909e1f1b6daf2db195710c30e5027f28f1d2714bb0608d82660"
    },
    "config_dump_txt/РегистрНакопления.ТоварыОрганизаций.МодульНабораЗаписей.txt": {
        "size": 36571,
        "sha256": "b3e41e214c37c1b13913203f4899d85027c32906f33980dc206ea75613f1c939"
    },
    "config_dump_txt/РегистрНакопления.ТоварыПереданные.МодульНабораЗаписей.txt": {
        "size": 42452,
        "sha256": "710ff6f596bb62f0434d446af6b1166af211fc1570b38cc765ecf6d997f23465"
    },
    "config_dump_txt/РегистрНакопления.ТоварыПолученные.МодульНабораЗаписей.txt": {
        "size": 11696,
        "sha256": "9b1fb8485dd4923884a6cd30d9ba5829f85d5adf45eef2e975427fc724c46503"
    },
    "config_dump_txt/РегистрСведений.ТоварыНаККМ.МодульНабораЗаписей.txt": {
        "size": 7934,
        "sha256": "6123607c3a33ae7f8cbf45eea48f6fce939fb24a58183589a7ba3f43934df4fe"
    },
    "config_dump_txt/РегистрСведений.ТоварыНаККМ.Форма.ФормаЗаполнения.Форма.Модуль.txt": {
        "size": 25946,
        "sha256": "870aef70629f3405a98be2a276bde85714a3f28cffeb4d8913bd212e5508841c"
    },
    "config_dump_txt/РегистрСведений.ТоварыНаККМ.Форма.ФормаСписка.Форма.Модуль.txt": {
        "size": 17669,
        "sha256": "ed4a48511e88c989fb86dbf2738104de968855264027fd8e9522d6ee3acd8bfb"
    },
    "config_dump_txt/РегистрСведений.ЦеныАТТ.МодульНабораЗаписей.txt": {
        "size": 770,
        "sha256": "f2a8ffd0361fbc2b13e8b9b7072633abf02b21a65a510589ba621598712a9f69"
    },
    "config_dump_txt/РегистрСведений.ЦеныНоменклатуры.МодульНабораЗаписей.txt": {
        "size": 770,
        "sha256": "f2a8ffd0361fbc2b13e8b9b7072633abf02b21a65a510589ba621598712a9f69"
    },
    "config_dump_txt/РегистрСведений.ЦеныНоменклатурыКонтрагентов.МодульНабораЗаписей.txt": {
        "size": 770,
        "sha256": "f2a8ffd0361fbc2b13e8b9b7072633abf02b21a65a510589ba621598712a9f69"
    },
    "config_dump_txt/Справочник.Номенклатура.МодульОбъекта.txt": {
        "size": 9191,
        "sha256": "044dbbde52cf8f249c8e0afda77bf709d9b01f79c19031870a087644617642e6"
    },
    "config_dump_txt/Справочник.Склады.МодульОбъекта.txt": {
        "size": 3221,
        "sha256": "f6c6c7999a7be2fa90e35efb250caaa41e5784d05c76de5154ce0936c85fda9a"
    },
    "config_dump_txt/Справочник.Склады.Форма.ФормаВыбора.Форма.Модуль.txt": {
        "size": 7,
        "sha256": "837885c8f8091aeaeb9ec3c3f85a6ff470a415e610b8ba3e49f9b33c9cf9d619"
    },
    "config_dump_txt/Справочник.Склады.Форма.ФормаГруппы.Форма.Модуль.txt": {
        "size": 800,
        "sha256": "67042dfda5683aead81b6055d19c4dba238341f9dd82f49c0e7cc0c19c5f10d1"
    },
    "config_dump_txt/Справочник.Склады.Форма.ФормаСписка.Форма.Модуль.txt": {
        "size": 4674,
        "sha256": "9a05ac5dc9ea31f97c46888f4d8385637ad3fc9aefc0f98c3585e555da3f39ba"
    },
    "config_dump_txt/Справочник.Склады.Форма.ФормаЭлемента.Форма.Модуль.txt": {
        "size": 23682,
        "sha256": "9ae64c923c196bfdef1d7d552e799bddcce992ef15e71c93593ff004267bcfe3"
    },
    "external/kmp4_delivery_report/src/КМП4/Ext/Help/ru.html": {
        "size": 8006,
        "sha256": "888b9fcd89ad551a20162f89b94eb4607abad9ec1569d4e08c5cac9d4f12b3b1"
    },
    "external/kmp4_delivery_report/src/КМП4/Ext/Help.xml": {
        "size": 232,
        "sha256": "c4fcd50d9f0c893c46288b57d8e62b18523145956b249b6ecd6c21718be49065"
    },
    "external/kmp4_delivery_report/src/КМП4/Ext/ObjectModule.bsl": {
        "size": 33722,
        "sha256": "35f52323c96a1203ebee76718eb1a1ae8c86722326e29cc64aad4713fc0e40e4"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/КонсольМенеджераПоПродажам/Ext/Form.bin": {
        "size": 750957,
        "sha256": "8c16cdd3cafd3a8c40bb4bfad142385e383528e1c70e36fe1a27e0e0227c115c"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/КонсольМенеджераПоПродажам.xml": {
        "size": 1614,
        "sha256": "f4366f672353037e88107185daa783e1dd0c47aefcea8a99f1399ffef5393c8d"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ПечатьИРассылкаПрайсЛистов/Ext/Form.bin": {
        "size": 74536,
        "sha256": "31f263d2b381fbeaf9ea805e3b8209fd05c009076e7c722b63fc5407d3ec2bd8"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ПечатьИРассылкаПрайсЛистов.xml": {
        "size": 1615,
        "sha256": "d491ed1d1712ed0d7c8a4e1ccf045188a92187e274759e7da6217845ff22c2bb"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/Форма/Ext/Form.bin": {
        "size": 45639,
        "sha256": "1ef20de0abedd5737a33a2aa12bcbadbcefac309d75abd74e0e13331c4687906"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/Форма.xml": {
        "size": 1527,
        "sha256": "69a8a97c65eca815052e13eb9e84d3bb2901af3f941f9fe7644bd6a38cb0b739"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ФормаВопросов/Ext/Form.bin": {
        "size": 5482,
        "sha256": "cbd1ba3a8ebce8020334e3770d02c67ce871a1efad71d845e694f1eb7a0803b2"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ФормаВопросов.xml": {
        "size": 1560,
        "sha256": "0ae208d8333b8d56b0871129f974ea63ad90303e5087fd1092d7cc7a66e85ed6"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ФормаЗагрузкиЗаявок/Ext/Form.bin": {
        "size": 48355,
        "sha256": "43ef5add608e030103a136a1868ee72595222b5e09a8fc6d0c8786c53ecee65e"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ФормаЗагрузкиЗаявок.xml": {
        "size": 1585,
        "sha256": "0f296f687f1579c2b79595d6ae858496a02871b2dd05311d19245d335057a21a"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ФормаОстатков/Ext/Form.bin": {
        "size": 18227,
        "sha256": "19ba542bff0358c7949d3674b8107130c096baa829bcdc35fe6e3f3f6d3dc99f"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ФормаОстатков.xml": {
        "size": 1560,
        "sha256": "0ae208d8333b8d56b0871129f974ea63ad90303e5087fd1092d7cc7a66e85ed6"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ФормаПерем/Ext/Form.bin": {
        "size": 12489,
        "sha256": "6dc05d87f1eef0991ddf709dfd844e1195c36e5067ce76ca8acfced0b217ad69"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ФормаПерем.xml": {
        "size": 1548,
        "sha256": "c1d2d3f68a3e31688e7b64b264c0276b8a1514dc9bf1ac204e0e5798f86be190"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ФормаПодборЦветовШрифтов/Ext/Form.bin": {
        "size": 71387,
        "sha256": "3ed419eebdbdfb46a3ca6f33b904bb12ddb7eaecc41a62aca3fb1d07ddbd1b1f"
    },
    "external/kmp4_delivery_report/src/КМП4/Forms/ФормаПодборЦветовШрифтов.xml": {
        "size": 1606,
        "sha256": "9b9f8ab4dd2f11548c0391aa876520d46bac71e3ea6ec028ab55b8f88d431aec"
    },
    "external/kmp4_delivery_report/src/КМП4/Templates/ПрайсЛист/Ext/Template.xml": {
        "size": 17204,
        "sha256": "64565644cd0deedcae892349ba0dc5cad82884abafc5ad682b7d3c741e63cebb"
    },
    "external/kmp4_delivery_report/src/КМП4/Templates/ПрайсЛист.xml": {
        "size": 1277,
        "sha256": "b50ce249eea2bfc220cffbfbbbc8d80f929c5008f0bc5c039b8d2c07e535431a"
    },
    "external/kmp4_delivery_report/src/КМП4/Templates/ПрайсЛистРуб/Ext/Template.xml": {
        "size": 12688,
        "sha256": "b2e6cfc0fb082ddc5d2c7b86c5d202b16ee7ae61a14cde048dbe25b7ca5ece65"
    },
    "external/kmp4_delivery_report/fixtures/valid_delivery_report.csv": {
        "size": 235,
        "sha256": "7a0c689e2cc4d3bc065b3bf06fee97d3a100f08df5dfee465b0e411f3c05b343"
    },
    "external/kmp4_delivery_report/src/КМП4/Templates/ПрайсЛистРуб.xml": {
        "size": 1290,
        "sha256": "94cc83c3173fae609cceba0d16b84a05aa9cfa596ed0dfdac3a8955c147220d4"
    },
    "external/kmp4_delivery_report/КМП4.xml": {
        "size": 82300,
        "sha256": "8f6f8483c8d1af70295fdf1e0139792cbddd71ec2c87ddf0b1a3b406889a2f98"
    }
}

TEN_MEBIBYTES = 10 * 1024 * 1024
ALLOWED_CONTROL_CODES = {0x09, 0x0A, 0x0D}
KMP4_MAGIC_HEADER = ["#KMP4_DELIVERY_REPORT", "v1"]
KMP4_REQUIRED_COLUMNS = [
    "order_id",
    "title",
    "customer_name",
    "status_code",
    "total_amount",
    "currency_code",
    "courier_id",
    "notes",
    "created_at",
    "updated_at",
]

def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(8192), b''):
            digest.update(chunk)
    return digest.hexdigest()


def check_kmp4_build_artifact(
    repo_root: Path, *, size_limit: int = TEN_MEBIBYTES
) -> list[str]:
    """Ensure the packaged KMP4 delivery report is present and under the limit."""

    errors: list[str] = []
    artifact = repo_root / 'build' / '1c' / 'kmp4_delivery_report.epf'
    if not artifact.exists():
        errors.append(
            "Missing build artifact: build/1c/kmp4_delivery_report.epf. "
            "Run `make 1c-pack-kmp4` to regenerate it before verifying."
        )
        return errors

    size = artifact.stat().st_size
    if size >= size_limit:
        errors.append(
            "build/1c/kmp4_delivery_report.epf exceeds the 10 MiB limit; "
            "regenerate the package or prune unused assets."
        )
    return errors


def iter_kmp4_csv_files(base: Path) -> Iterator[Path]:
    """Yield CSV artifacts that should comply with the KMP4 export contract."""

    csv_root = base / 'external' / 'kmp4_delivery_report'
    if not csv_root.exists():
        return
    for path in csv_root.rglob('*.csv'):
        if path.is_file():
            yield path


def _detect_forbidden_characters(path: Path, payload: str) -> list[str]:
    errors: list[str] = []
    line = 1
    column = 1
    for char in payload:
        code = ord(char)
        if char == '\n':
            line += 1
            column = 1
            continue
        if char == '\r':
            column = 1
            continue
        if code < 32 and code not in ALLOWED_CONTROL_CODES:
            errors.append(
                f"Forbidden control character U+{code:04X} at line {line}, column {column} in {path.as_posix()}."
            )
        column += 1
    return errors


def validate_kmp4_csv_file(path: Path) -> list[str]:
    """Validate forbidden characters and header structure for a CSV export."""

    errors: list[str] = []
    text = path.read_text(encoding='utf-8-sig')
    errors.extend(_detect_forbidden_characters(path, text))
    if errors:
        return errors

    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return [f"CSV artifact is empty: {path}"]

    magic_row = rows[0]
    if magic_row != KMP4_MAGIC_HEADER:
        errors.append(
            f"Invalid KMP4 header in {path.as_posix()}: expected {KMP4_MAGIC_HEADER}, got {magic_row}."
        )
        return errors

    if len(rows) < 2:
        errors.append(f"CSV artifact {path} is missing the column header row.")
        return errors

    header_row = rows[1]
    missing = [column for column in KMP4_REQUIRED_COLUMNS if column not in header_row]
    if missing:
        errors.append(
            f"CSV artifact {path} is missing required columns: {', '.join(missing)}."
        )
    return errors


def validate_tree(repo_root: Path) -> list[str]:
    errors: list[str] = []
    base = repo_root / '1c'
    if not base.exists():
        errors.append(f"Missing directory: {base}")
        return errors

    errors.extend(check_kmp4_build_artifact(repo_root))

    for relative, metadata in sorted(MANIFEST.items()):
        expected_size = int(metadata['size'])
        expected_hash = str(metadata['sha256'])
        target = base / relative
        if not target.exists():
            errors.append(f"Missing file: {relative}")
            continue
        size = target.stat().st_size
        if size != expected_size:
            errors.append(
                f"Size mismatch for {relative}: expected {expected_size}, got {size}"
            )
            continue
        actual_hash = sha256sum(target)
        if actual_hash != expected_hash:
            errors.append(
                f"Hash mismatch for {relative}: expected {expected_hash}, got {actual_hash}"
            )

    for csv_path in iter_kmp4_csv_files(base):
        errors.extend(validate_kmp4_csv_file(csv_path))

    expected_paths = {(base / rel).resolve() for rel in MANIFEST}
    actual_paths = {
        path.resolve()
        for folder in ('config_dump_txt', 'external/kmp4_delivery_report')
        for path in (base / folder).rglob('*')
        if path.is_file()
    }
    extras = sorted(p for p in actual_paths - expected_paths)
    for extra in extras:
        rel = extra.relative_to(base)
        errors.append(f"Unexpected file present: {rel.as_posix()}")

    return errors


def main(argv: Iterable[str]) -> int:
    parser = argparse.ArgumentParser(
        description='Validate the 1C asset tree against the repository manifest.'
    )
    parser.add_argument(
        '--repo-root',
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help='Override the repository root path.',
    )
    args = parser.parse_args(list(argv))

    errors = validate_tree(args.repo_root)
    if errors:
        for message in errors:
            print(message, file=sys.stderr)
        return 1
    print('1C asset tree is valid.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
