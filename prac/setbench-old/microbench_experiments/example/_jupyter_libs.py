from run_experiment import *
import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns
from IPython.display import display

plt.style.use('dark_background')
disable_tee_stdout()
disable_logfile_close()
args = do_all('_user_experiment.py --testing --no-compile --no-run --no-createdb'.split(' '))

#########################################################################
#### Some convenience functions for use in a jupyter notebook...
#########################################################################

def select_to_dataframe(txn):
    return pd.read_sql_query(txn, get_connection())

def add_legend_and_reshape(g, loc='lower center', ncol=5, bottom=0.14, size=(8, 6)):
    g.add_legend(loc=loc, ncol=ncol)
    g.fig.subplots_adjust(bottom=bottom, top=1, left=0, right=1)
    g.fig.set_size_inches(size[0], size[1])

## markers, palette, dashes and sizes define lists of values to be used for the various series
## (sane defaults are supplied)
def get_series_styles(series, markers=['^', 'o', 's', '+', 'x', 'v', '*', 'X', '|', '.', 'd'], palette=None, dashes=[''], sizes=[1], plot_func=sns.lineplot):
    ## construct mappings from each series value to round-robin choices from the above
    if isinstance(series, str):
        series_distinct = select_distinct_field(series)
    if not palette:
        palette = sns.color_palette("colorblind", len(series_distinct))
    plot_style_kwargs = dict(palette=dict())
    for i, series in zip(range(len(series_distinct)), series_distinct):
        plot_style_kwargs['palette'][series] = palette[i % len(palette)]

    if plot_func == sns.lineplot:
        plot_style_kwargs['markers'] = dict()
        plot_style_kwargs['sizes'] = dict()
        plot_style_kwargs['dashes'] = dict()
        for i, series in zip(range(len(series_distinct)), series_distinct):
            plot_style_kwargs['markers'][series] = markers[i % len(markers)]
            plot_style_kwargs['sizes'][series] = sizes[i % len(sizes)]
            plot_style_kwargs['dashes'][series] = dashes[i % len(dashes)]

    return plot_style_kwargs

def plot_5d(row, col, series, x, y, data=None, where='', series_styles=None, plot_func=sns.lineplot, facetgrid_kwargs=dict()):
    txn = 'SELECT {}, {}, {}, {}, {} FROM DATA {}'.format(row, col, series, x, y, where)
    if data is None: data = select_to_dataframe(txn)
    #display(df)

    if len(facetgrid_kwargs.keys()) == 0:
        facetgrid_kwargs['margin_titles'] = True

    g = sns.FacetGrid(data=data, row=row, col=col, **facetgrid_kwargs)

    if not series_styles:
        series_styles = get_series_styles(series, plot_func=plot_func)

    def plot_5d_facet(x, y, series, **kwargs):
        if plot_func == sns.lineplot: series_styles['style'] = series
        #display(x, y, series, series_styles, kwargs)
        plot_func(x=x, y=y, hue=series, **series_styles, **kwargs)

    g.map(plot_5d_facet, x, y, series)

    add_legend_and_reshape(g)

def filter_df_by_columns(df, column_filter=cf_any):
    ## compute a bitmap that dictates which columns should be included (not filtered out)
    headers = list(df.columns.values)
    # print(headers)
    include_col_indexes = []
    for i, col_name in zip(range(len(headers)), headers):
        col_values = list(df[headers[i]])
        # print('col_name={} col_values={}'.format(col_name, col_values))
        if column_filter(col_name, col_values):
            include_col_indexes.append(i)
    return df[ [headers[i] for i in include_col_indexes] ]

def plot_to_axes(x, y, series='', where='', kind='line', ax=None, display_data=False):
    ## TODO: run sanity checks on this plot...
    headers, records = get_records_plot(series, x, y, where)
    csv = table_to_str(records, headers)
    df = pd.read_csv(io.StringIO(csv), sep=' ')

    if display_data == 'full':
        df_full = select_to_dataframe('select * from data {}'.format(where))
        display(df_full)
    elif display_data == 'diff':
        df_full = select_to_dataframe('select * from data {}'.format(where))
        df_diff = filter_df_by_columns(df_full, column_filter=cf_and(cf_not_intrinsic, cf_not_identical))
        display(df_diff)
    elif display_data == 'diff2':
        df_full = select_to_dataframe('select * from data {}'.format(where))
        df_diff = filter_df_by_columns(df_full, column_filter= \
                cf_andl([ \
                    cf_not_in([series, x, y]), \
                    cf_run_param, \
                    cf_not_intrinsic, \
                    cf_not_identical
                ]))
        if len(df_diff.columns.values) > 0:
            display(df_diff)
    elif display_data:
        display(df)

    pivot_table_kwargs = dict()
    if series != '':
        pivot_table_kwargs['columns'] = series

    plot_kwargs = dict()
    plot_kwargs['kind'] = kind
    if ax != None:
        plot_kwargs['ax'] = ax

    table = pd.pivot_table(df, values=y, index=x, aggfunc=np.mean, **pivot_table_kwargs)
    table.plot(**plot_kwargs)

def plot_to_axes_dict(x, y, filter_values, series='', ax=None, display_data=False):
    plot_to_axes(x, y, series=series, where=get_where_from_dict(filter_values), ax=ax, display_data=display_data)

def plot_to_axes_grid(result_dict, replacement_values, series, x, y, row_field, row_values, row_index, column_field, column_values, column_index):
    # print('get_table: {}'.format(locals()))
    if 'axes' not in result_dict.keys():
        fig, axes = plt.subplots(nrows=len(row_values), ncols=len(column_values))
        result_dict['axes'] = axes
        result_dict['fig'] = fig

    ## plot in one axis grid cell
    where = get_where_from_dict(replacement_values)
    headers, records = get_records_plot(series, x, y, where)
    csv = table_to_str(records, headers)
    df = pd.read_csv(io.StringIO(csv), sep=' ')
    table = pd.pivot_table(df, values=y, index=x, columns=series, aggfunc=np.mean)
    table.plot(ax=result_dict['axes'][row_index,column_index])

## calls func(func_arg, replacement_values, series_field, x_field, y_field, column_field, column_values, column_index, row_field, row_values, row_index)
def table_of_plots_lambda(replacement_values, series_field, x_field, y_field, row_field, column_field, func, func_arg):
    tee()
    tee('table_of_plots_lambda: replacement_values = {}'.format(replacement_values))

    ## if this set of replacement_values yields no actual data, prune this TABLE
    if get_num_rows(replacement_values) == 0:
        tee('pruning table under replacement_values {}"'.format(replacement_values))
        return

    # column_field = page_set['column_field']
    column_field_values = [''] if (column_field == '') else select_distinct_field_dict(column_field, replacement_values) #g['run_params'][column_field]
    # row_field = page_set['row_field']
    row_field_values = [''] if (row_field == '') else select_distinct_field_dict(row_field, replacement_values) #g['run_params'][row_field]

    for rix, rval in zip(range(len(row_field_values)), row_field_values):
        replacement_values[row_field] = str(rval)

        if get_num_rows(replacement_values) == 0:          ## if this set of replacement_values yields no actual data, prune this ROW
            tee('pruning row {} under replacement_values {}"'.format(rval, replacement_values))
        else:
            for cix, cval in zip(range(len(column_field_values)), column_field_values):
                replacement_values[column_field] = str(cval)

                if get_num_rows(replacement_values) == 0:  ## if this set of replacement_values yields no actual images, prune this CELL
                    tee('pruning cell {} in row {} under replacement_values {}"'.format(cval, rval, replacement_values))
                else:
                    func(func_arg, replacement_values, series_field, x_field, y_field, row_field, row_field_values, rix, column_field, column_field_values, cix)

                del replacement_values[column_field]

        del replacement_values[row_field]

# def build_page_lambda(replacement_values, page_set, func, func_arg):
#     tee()
#     tee('build_page_lambda: replacement_values = {}'.format(replacement_values))

#     table_field = page_set['table_field']
#     table_field_values = [''] if (table_field == '') else g['run_params'][table_field]
#     for i, table_field_value in zip(len(table_field_values), table_field_values):
#         if table_field != '': replacement_values[table_field] = table_field_value
#         table_of_plots_lambda(replacement_values, page_set, table_field, table_field_values, i, func, func_arg)
#         if table_field != '': del replacement_values[table_field]

# def build_page_set_lambda(i, page_set):
#     tee()
#     tee('page_set {}'.format(i))
#     tee_pp(page_set)

#     to_enumerate = dict((k, g['run_params'][k]) for k in page_set['page_field_list'])
#     enumerated_values = dict()
#     for_all_combinations(0, to_enumerate, enumerated_values, build_html_page, page_set)
