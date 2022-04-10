import pyTSL
import sys
from os import getcwd
from os.path import join
from urllib.request import pathname2url
from PyQt5.QtWidgets import QApplication, QDesktopWidget
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, Qt, QThread, pyqtSignal
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from numpy import array
import talib as ta
from typing import List, Union
from pyecharts.charts import Kline, Line, Bar, Grid
from pyecharts import options as opts
from pyecharts.charts import Line
from pyecharts.globals import ThemeType

c = pyTSL.Client('TSlogin.ini')
c.login()

def get_data(stk_code='SH600006', cycle='cy_1m()', begt='20220201T', endt='now()'):
    code = '''
    SetSysParam("Cycle",{cycle});
    SetSysParam("bRate",0);
    SetSysParam("RateDay",0.0);
    SetSysParam("Precision",2);
    SetSysParam("profiler",0);
    SetSysParam("ReportMode",0);
    SetSysParam("EmptyMode",0);
    SetSysParam("CalcCTRLWord",0);
    SetSysParam("BegT",{begt});
    SetSysParam("EndT",{endt});
    SetSysParam("TimeIndex",1);
    SetSysParam("LanguageID",0);
    return 
    QueryWithPeriod("","{stk_code}",@True,"","开盘价",@open(),
    "收盘价",@close(),
    "最低价",@low(),
    "最高价",@high(),
    "成交量",@vol());
    '''.format(
        cycle=cycle,
        stk_code=stk_code,
        begt=begt,
        endt=endt
    )
    
    global c
    r = c.exec(code)
    
    result = r.value()
    
    result_keys = list(result[0].keys())

    stk_name = result_keys[0].split('@')[0]

    col_code = [
        '时间',
        (stk_name + '@开盘价'),
        (stk_name + '@收盘价'),
        (stk_name + '@最低价'),
        (stk_name + '@最高价'),
        (stk_name + '@成交量')
    ]

    res = {}

    res['values'] = [[x[col_code[i]] for i in range(6)] for x in result]
    res['categoryData'] = []
    res['volumes'] = []

    for i, tick in enumerate(res['values']):
        this_time = tick[0]
        if begt == 'today()':
            this_time = this_time[11:]
        res['categoryData'].append(this_time)
        res['volumes'].append([i, tick[4], 1 if tick[1] > tick[2] else -1])

    return res, stk_name


def calculate_ma(day_count: int, data):
    result: List[Union[float, str]] = []
    for i in range(len(data["values"])):
        if i < day_count:
            result.append("-")
            continue
        sum_total = 0.0
        for j in range(day_count):
            sum_total += float(data["values"][i - j][1])
        result.append(abs(float("%.3f" % (sum_total / day_count))))
    return result


def get_kline(
        stk_code='SH600006',
        begt='today()', endt='now()',
        cycle='cy_1m()',
        MAs=[5, 10, 20, 30],
        mode='init'):
    chart_data, stk_name = get_data(stk_code, cycle, begt, endt)
    this_close = array([x[2] for x in chart_data['values']])
    this_x = chart_data["categoryData"]
    kline_data = [data[1:-1] for data in chart_data["values"]]
    kline = (
        Kline()
            .add_xaxis(xaxis_data=chart_data["categoryData"])
            .add_yaxis(
            series_name=stk_name,
            y_axis=kline_data,
            itemstyle_opts=opts.ItemStyleOpts(
                color="#ec0000",
                color0="#02ece5",
                border_color="#8A0000",
                border_color0="#02ece5",
            ),
        )
            .set_global_opts(
            visualmap_opts=opts.VisualMapOpts(
                is_show=False,
                dimension=2,
                series_index=5,
                is_piecewise=True,
                pieces=[
                    {"value": 1, "color": "#3fdafd"},
                    {"value": -1, "color": "#ec0000"},
                ],
            ),
            xaxis_opts=opts.AxisOpts(
                is_show=True,
                axispointer_opts=opts.AxisPointerOpts(
                    is_show=True,
                    type_="shadow",
                    label=opts.LabelOpts(
                        background_color='#000000'
                    )
                )
            ),

            yaxis_opts=opts.AxisOpts(
                is_scale=True,
                splitarea_opts=opts.SplitAreaOpts(
                    is_show=False, areastyle_opts=opts.AreaStyleOpts(opacity=1)
                ),
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="cross",
                background_color="rgba(245, 245, 245, 0.8)",
                border_width=1,
                border_color="#ccc",
                textstyle_opts=opts.TextStyleOpts(color="#000"),
            ),

        )
    )

    # MA
    line = Line(init_opts=opts.InitOpts(theme=ThemeType.DARK)).add_xaxis(xaxis_data=chart_data["categoryData"])
    for ma_para in MAs:
        line.add_yaxis(
            series_name="MA" + str(ma_para),
            y_axis=calculate_ma(day_count=ma_para, data=chart_data),
            is_smooth=True,
            is_hover_animation=False,
            linestyle_opts=opts.LineStyleOpts(width=2, opacity=1),
            label_opts=opts.LabelOpts(is_show=False),
        )
    line.set_global_opts(
        tooltip_opts=opts.TooltipOpts(
            trigger="axis",
            axis_pointer_type="cross",
            background_color="rgba(245, 245, 245, 0.8)",
            border_width=1,
            border_color="#ccc",
            textstyle_opts=opts.TextStyleOpts(color="#000"),
        ),
        xaxis_opts=opts.AxisOpts(
            type_="category")
    )

    kline_over_line = kline.overlap(line)
    return kline_over_line, this_x, this_close


def get_MACD(this_x, this_close, para=None):
    if para is None:
        para = [12, 26, 9]
    # line_DIF, line_DEA, line_MACD
    MACD_val = {}
    MACD_val['DIF'], MACD_val['DEF'], MACD_val['MACD'] = ta.MACD(this_close, fastperiod=para[0], slowperiod=para[1],
                                                                 signalperiod=para[2])
    line_MACD = Line(init_opts=opts.InitOpts(theme=ThemeType.DARK)).add_xaxis(xaxis_data=this_x)
    line_color = {
        'DIF': '#ffffff',
        'DEF': '#E3873C'
    }
    for col_name in ['DIF', 'DEF']:
        line_MACD.add_yaxis(
            series_name=col_name,
            # color=line_color[col_name],
            y_axis=MACD_val[col_name],
            is_smooth=True,
            is_hover_animation=False,
            linestyle_opts=opts.LineStyleOpts(
                # color=line_color[col_name],
                width=2,
                opacity=1, ),
            label_opts=opts.LabelOpts(is_show=False),
        )

    line_MACD.set_global_opts(
        tooltip_opts=opts.TooltipOpts(
            trigger="axis",
            axis_pointer_type="cross",
            background_color="rgba(245, 245, 245, 0.8)",
            border_width=1,
            border_color="#ccc",
            textstyle_opts=opts.TextStyleOpts(color="#000"),
        ),
        xaxis_opts=opts.AxisOpts(
            type_="category",
            axispointer_opts=opts.AxisPointerOpts(
                is_show=True,
                type_="shadow",
                label=opts.LabelOpts(
                    background_color='#000000'
                )
            )
        ),
        yaxis_opts=opts.AxisOpts(
            is_scale=True,
            splitarea_opts=opts.SplitAreaOpts(
                is_show=False, areastyle_opts=opts.AreaStyleOpts(opacity=1)
            ),
        )
    )

    bar_data = []
    for idx, x in enumerate(MACD_val['MACD']):
        bar_data.append(
            opts.BarItem(
                name=this_x[idx],
                value=x,
                itemstyle_opts=opts.ItemStyleOpts(color="#ec0000") if x > 0 else opts.ItemStyleOpts(color="#02ece5"),
            )
        )

    bar = (
        Bar()
            .add_xaxis(xaxis_data=this_x)
            .add_yaxis(
            series_name="MACD",
            y_axis=bar_data,
            label_opts=opts.LabelOpts(is_show=False),
        )
            .set_global_opts(
            xaxis_opts=opts.AxisOpts(
                type_="category",
                is_scale=True,
                grid_index=1,
                boundary_gap=False,
                axisline_opts=opts.AxisLineOpts(is_on_zero=False),
                axistick_opts=opts.AxisTickOpts(is_show=False),
                splitline_opts=opts.SplitLineOpts(is_show=False),
                axislabel_opts=opts.LabelOpts(is_show=False),
                split_number=20,
                min_="dataMin",
                max_="dataMax",
            ),
            yaxis_opts=opts.AxisOpts(
                grid_index=1,
                is_scale=True,
                split_number=2,
                axislabel_opts=opts.LabelOpts(is_show=False),
                axisline_opts=opts.AxisLineOpts(is_show=False),
                axistick_opts=opts.AxisTickOpts(is_show=False),
                splitline_opts=opts.SplitLineOpts(is_show=False),
            ),
            legend_opts=opts.LegendOpts(is_show=False),
        )
    )

    return line_MACD.overlap(bar)


def get_RSI(this_x, this_close, para=None):
    if para is None:
        para = [6]
    # RSI's
    RSI_val = {}
    for this_para in para:
        RSI_val[this_para] = ta.RSI(this_close, timeperiod=this_para)

    line_RSI = Line(init_opts=opts.InitOpts(theme=ThemeType.DARK)).add_xaxis(xaxis_data=this_x)

    line_color = [
        '#FFFF00'
    ]
    for line_idx, this_para in enumerate(para):
        line_RSI.add_yaxis(
            series_name="RSI_" + str(this_para),
            y_axis=RSI_val[this_para],
            is_smooth=True,
            is_hover_animation=False,
            linestyle_opts=opts.LineStyleOpts(
                color=line_color[line_idx],
                width=2,
                opacity=1, ),
            label_opts=opts.LabelOpts(is_show=False),
        )

    line_RSI.add_yaxis(
        series_name="50_baseline",
        y_axis=[50 + x * 0 for x in RSI_val[para[0]]],
        is_smooth=True,
        is_hover_animation=False,
        linestyle_opts=opts.LineStyleOpts(
            color='#ffffff',
            width=1,
            opacity=0.5, ),
        label_opts=opts.LabelOpts(is_show=False),
    )

    line_RSI.set_global_opts(
        tooltip_opts=opts.TooltipOpts(
            trigger="axis",
            axis_pointer_type="cross",
            background_color="rgba(245, 245, 245, 0.8)",
            border_width=1,
            border_color="#ccc",
            textstyle_opts=opts.TextStyleOpts(color="#000"),
        ),
        xaxis_opts=opts.AxisOpts(
            type_="category",
            axispointer_opts=opts.AxisPointerOpts(
                is_show=True,
                type_="shadow",
                label=opts.LabelOpts(
                    background_color='#000000'
                )
            )
        ),
        yaxis_opts=opts.AxisOpts(
            is_scale=True,
            splitarea_opts=opts.SplitAreaOpts(
                is_show=False, areastyle_opts=opts.AreaStyleOpts(opacity=1)
            ),
        )
    )

    return line_RSI


def draw_charts(stk_code='SH600006', lines_cycle=['cy_1m()', 'cy_5m()', 'cy_30m()'], begt='20220201T', endt='now()',
                mode='init', MACD_para=None, RSI_para=None):
    assert mode in ['init', 'update']

    ## 加入 DataZoom
    n_lines = len(lines_cycle)
    ## 创建grid
    grid_chart = Grid(
        init_opts=opts.InitOpts(
            width="1500px",
            height="1000px",
            animation_opts=opts.AnimationOpts(animation=False),
        )
    )
    line_heigh = 85 / n_lines
    line_pos_top = [3 + idx * int(line_heigh) for idx in range(n_lines)]
    for idx, cycle in enumerate(lines_cycle):
        line, this_x, this_close = get_kline(stk_code, begt, endt, cycle, mode=mode)
        line.set_global_opts(
            title_opts=opts.TitleOpts(
                title=cycle,
                pos_top=str(line_pos_top[idx]) + '%',
                title_textstyle_opts=opts.TextStyleOpts(color='#ffffff'),
            ),
            legend_opts=opts.LegendOpts(
                is_show=(idx == 0),
                pos_top=str(line_pos_top[idx]) + '%',
                textstyle_opts=opts.TextStyleOpts(color='#ffffff'),
            ),
            datazoom_opts=[
                opts.DataZoomOpts(
                    is_show=False,
                    type_="inside",
                    xaxis_index=list(range(n_lines * 3)),
                    pos_bottom="8%",
                    range_start=90,
                    range_end=100,
                    filter_mode="None"
                ),
                opts.DataZoomOpts(
                    is_show=True,
                    type_="slider",
                    xaxis_index=list(range(n_lines * 3)),
                    pos_bottom="8%",
                    range_start=90,
                    range_end=100,
                    filter_mode="None",
                )
            ]
        )

        line_MACD = get_MACD(this_x, this_close, para=MACD_para).set_global_opts(
            title_opts=opts.TitleOpts(
                pos_top=str(line_pos_top[idx] + line_heigh * 0.45) + '%',
                title="MACD",
                title_textstyle_opts=opts.TextStyleOpts(color='#ffffff'),
            ),
            legend_opts=opts.LegendOpts(
                is_show=(idx == 0),
                textstyle_opts=opts.TextStyleOpts(color='#ffffff'),
            ),
        )

        line_RSI = get_RSI(this_x, this_close, para=RSI_para).set_global_opts(
            title_opts=opts.TitleOpts(
                pos_top=str(line_pos_top[idx] + line_heigh * 0.7) + '%',
                title="RSI",
                title_textstyle_opts=opts.TextStyleOpts(color='#ffffff'),
            ),
            legend_opts=opts.LegendOpts(
                is_show=False,
                textstyle_opts=opts.TextStyleOpts(color='#ffffff'),
            ),
        )

        grid_chart.add(
            line,
            grid_opts=opts.GridOpts(
                z_level=5,
                pos_top=str(line_pos_top[idx]) + '%',
                height=str(line_heigh * 0.35) + "%",
            ),

        )

        grid_chart.add(
            line_MACD,
            grid_opts=opts.GridOpts(
                pos_top=str(line_pos_top[idx] + line_heigh * 0.45) + '%',
                height=str(line_heigh * 0.15) + "%"),
        )

        grid_chart.add(
            line_RSI,
            grid_opts=opts.GridOpts(
                pos_top=str(line_pos_top[idx] + line_heigh * 0.7) + '%',
                height=str(line_heigh * 0.15) + "%"),
        )

        del line

    return grid_chart


class LoadData(QThread):
    mysignal = pyqtSignal(tuple)

    def __init__(self, stk_code, begt, endt, mode, cycle, MACD_para, RSI_para):
        super(LoadData, self).__init__()
        self.para = (stk_code, begt, endt, mode, cycle, MACD_para, RSI_para)

    def run(self):
        stk_code, begt, endt, mode, cycle, MACD_para, RSI_para = self.para
        c = draw_charts(stk_code=stk_code, lines_cycle=cycle.split(','), begt=begt, endt=endt, mode=mode,
                        MACD_para=[int(x) for x in MACD_para.split(',')], RSI_para=[int(RSI_para)])
        msg = c.dump_options().replace('\n', '')
        msg = msg.replace('(', '')
        msg = msg.replace(')', '')
        self.mysignal.emit((msg, mode))


my_thread = None


class CallHandler(QObject):
    def __init__(self):
        super(CallHandler, self).__init__()

    @pyqtSlot(str, str, str, str, str, str, str, result=str)
    def build_chart(self, stk_code, begt, endt, mode, cycle, MACD_para, RSI_para):
        global my_thread
        if my_thread is not None:
            my_thread.quit()
            my_thread.wait()
        my_thread = LoadData(stk_code, begt, endt, mode, cycle, MACD_para, RSI_para)  # 步骤2. 主线程连接子线
        my_thread.mysignal.connect(build_chart_update)  # 自定义信号连接
        my_thread.start()  # 步骤3 子线程开始执行run函数


def build_chart_update(a):
    msg, mode = a
    view.page().runJavaScript("window.build_chart_reaction('%s', '%s')" % (msg, mode))
    return


class WebEngine(QWebEngineView):
    def __init__(self):
        super(WebEngine, self).__init__()
        self.setContextMenuPolicy(Qt.NoContextMenu)  # 设置右键菜单规则为自定义右键菜单
        # self.customContextMenuRequested.connect(self.showRightMenu)  # 这里加载并显示自定义右键菜单，我们重点不在这里略去了详细带吗

        self.setWindowTitle('WindAssistant')
        self.resize(1800, 1000)
        cp = QDesktopWidget().availableGeometry().center()


if __name__ == '__main__':

    app = QApplication(sys.argv)
    view = WebEngine()
    channel = QWebChannel()
    handler = CallHandler()  # 实例化QWebChannel的前端处理对象
    channel.registerObject('PyHandler', handler)  # 将前端处理对象在前端页面中注册为名PyHandler对象，此对象在前端访问时名称即为PyHandler'
    view.page().setWebChannel(channel)  # 挂载前端处理对象
    url_string = pathname2url(
        join(getcwd(), r".\templates\index.html"))  # 加载本地html文件
    view.load(QUrl(url_string))
    view.show()
    sys.exit(app.exec_())
