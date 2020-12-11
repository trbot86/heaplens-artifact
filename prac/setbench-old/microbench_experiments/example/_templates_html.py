template_html = '''
<html>
  <head>
    <style>
      a:link {
        color: #8080FF;
      }
      a:visited {
        color: #E0E0B0;
      }
      a:hover {
        color: #D0CC00;
      }
      a:active {
        color: #D0CC00;
      }
      a {
        font-family: monospace;
      }
      pre {
        display: inline;
        font-family: monospace;
      }
      body {
        font-size: 1em !important;
        color: #b0b4b8 !important;
        font-family: Arial !important;
      }
      th {
        text-align: center;
        background-color: #101316;
        font-size: 22px;
        padding: 8px;
      }
      td {
        text-align: center;
        background-color: #151719;
        font-size: 22px;
      }
      .sidenav {
        height: 100%;
        width: 220px; /* sidebar width */
        position: fixed;
        z-index: 1;
        top: 0;
        left: 0;
        background-color: #111;
        overflow-x: hidden;
        padding-top: 0px;
      }
      .sidenav a {
        padding: 4px 4px 4px 4px;
        text-decoration: none;
        font-size: 18px;
        color: #818181;
        display: block;
      }
      .sidenav a:hover {
        color: #f1f1f1;
      }
      .main {
        margin-left: 220px; /* same as sidebar width */
        padding: 0px 0px;
      }
    </style>
  </head>
  <body bgcolor="#252729">
    <div class="sidenav">
{template_nav_link_list}
    </div>
    <div class="main">
{template_content}
    </div>
  </body>
</html>
'''
template_nav_link = '''
      <a href="{nav_link_href}">{nav_link_text}</a>'''

template_table = '''
      {template_table_title}
      <table>
        <tr>{template_table_th_list}
        </tr>{template_table_tr_list}
      </table>
'''
template_table_th = '''
          <th>{table_th_text}</th>'''
template_table_tr = '''
        <tr>{template_table_tr_td_list}</tr>'''
template_table_tr_td = '''
          <td>{table_tr_td_text}</td>'''
