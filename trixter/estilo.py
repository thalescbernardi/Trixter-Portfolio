"""Folhas de estilo da interface.

Os seletores são os mesmos que a tela já usava. Cada folha continua
sendo publicada no momento em que a tela correspondente aparece.
"""
import base64
from pathlib import Path

import streamlit as st


def folha(css):
    return f"<style>\n{css}\n</style>"


def publicar(css):
    st.html(folha(css))

ESTILO_BASE = """\
    .stButton > button {
         border-radius: 10px;
         font-weight: 600;
    }


    [data-testid="stSidebar"] > div:first-child {
         background-color: #FFF8DC;
    }


    [data-testid="stSidebar"] {
         border-right: 1px solid rgba(198, 161, 91, 0.22);
    }


    [data-testid="stMetric"] {
         background-color: #F7F4EE;
         border: 1px solid rgba(198, 161, 91, 0.30);
         border-radius: 12px;
         padding: 12px;
    }

    [data-testid="stBaseButton-primary"] {
         background-color: #C6A15B !important;
         border-color: #C6A15B !important;
         color: #181818 !important;
    }

    [data-testid="stBaseButton-primary"]:hover {
         background-color: #B89047 !important;
         border-color: #B89047 !important;
         color: #181818 !important;
    }

    [data-testid="stBaseButton-primaryFormSubmit"] {
         background-color: #C6A15B !important;
         border-color: #C6A15B !important;
         color: #181818 !important;
    }

    [data-testid="stBaseButton-primaryFormSubmit"]:hover {
         background-color: #B89047 !important;
         border-color: #B89047 !important;
         color: #181818 !important;
    }

    [data-testid="stBaseButton-secondary"] {
         background-color: #FFFDF8 !important;
         border: 1px solid #C6A15B !important;
         color: #A67C00 !important;
    }

    [data-testid="stBaseButton-secondary"]:hover {
         background-color: #F7F4EE !important;
         border-color: #A67C00 !important;
         color: #8B6A00 !important;
    }

    [data-testid="stBaseButton-secondary"]:focus,
    [data-testid="stBaseButton-secondary"]:active {
         background-color: #FFFDF8 !important;
         border-color: #C6A15B !important;
         color: #A67C00 !important;
         box-shadow: none !important;
    }


    div[data-baseweb="input"] {
         border-color: #C6A15B !important;
    }

    div[data-baseweb="input"]:focus-within {
         border-color: #C6A15B !important;
         box-shadow: 0 0 0 1px #C6A15B !important;
    }

    div[data-baseweb="select"] > div {
         border-color: #C6A15B !important;
    }

    div[data-baseweb="select"]:focus-within > div {
         border-color: #C6A15B !important;
         box-shadow: 0 0 0 1px #C6A15B !important;
    }

    div[data-testid="stNumberInput"] div[data-baseweb="input"] {
         border-color: #C6A15B !important;
    }

    div[data-testid="stNumberInput"] div[data-baseweb="input"]:focus-within {
         border-color: #C6A15B !important;
         box-shadow: 0 0 0 1px #C6A15B !important;
    }

    div[data-testid="stNumberInput"] div:has(> div[data-baseweb="input"]) {
         border-color: #C6A15B !important;
         box-shadow: none !important;
    }

    div[data-testid="stNumberInput"] div:has(> div[data-baseweb="input"]):focus-within {
         border-color: #C6A15B !important;
         box-shadow: 0 0 0 1px #C6A15B !important;
    }

    div[data-testid="stTextInput"] div[data-baseweb="input"] {
         border-color: #C6A15B !important;
    }

    div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
         border-color: #C6A15B !important;
         box-shadow: 0 0 0 1px #C6A15B !important;
    }

    div[data-testid="stDateInput"] div[data-baseweb="input"] {
         border-color: #C6A15B !important;
    }

    div[data-testid="stDateInput"] div[data-baseweb="input"]:focus-within {
         border-color: #C6A15B !important;
         box-shadow: 0 0 0 1px #C6A15B !important;
    }


    .st-key-btn_confirmar_entrada button,
    .st-key-btn_confirmar_entrada button * {
       color: #FFFFFF !important;
    }

    .st-key-btn_salvar_nova_conta button,
    .st-key-btn_salvar_nova_conta button * {
       color: #FFFFFF !important;
    }


    /*
    [data-testid="stHeader"] {
       background: transparent !important;
       height: 0rem !important;
    }

    [data-testid="stToolbar"] {
       display: none !important;
    }
    */

    .block-container {
       padding-top: 0rem !important;
    }

    .st-key-forgot_password_wrap button {
       border: none !important;
       background: transparent !important;
       box-shadow: none !important;
       color: #8f8174 !important;
       font-size: 13px !important;
       padding: 2px 0 !important;
       min-height: 0 !important;
    }

    .trixter-icon text {
       fill: FFFFFF !important;
    }

    .st-key-btn_entrar button {
      background: linear-gradient(
        135deg,
        #8F5E12 0%,
        #B98224 45%,
        #D6A84E 100%
    )  !important;

      color: #FFFFFF !important;
      border: 1px solid #C28B2C !important;
      box-shadow:
        0 3px 8px rgba(120, 75, 10, 0.20),
        inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
    }

    .st-key-btn_entrar button:hover {
      background: linear-gradient(
        135deg,
        #9C6818 0%,
        #C18B2C 45%,
        #E0B55B 100%
    )   !important;
    }

    .frase-esquerda {
       position: fixed;
       left: 7%;
       top: 20%;
       width: 230px;
       font-size: 28px;
       font-weight: 400;
       line-height: 1.18;
       color: #172033;
       text-align: left;
       z-index: 1;
    }

    .frase-esquerda span {
       color: #A67C00;
       font-weight: 500;
    }

    .frase-direita {
       position: fixed;
       right: 2%;
       top: 15%;
       font-size: 21px;
       line-height: 1.25;
       color: #172033;
    }

    .frase-direita .dourado {
       color: #A67C00;
       font-weight: 600;
    }

    [data-testid="stWidgetLabel"] p {
       color: #172033 !important;
       font-weight: 500 !important;
    }

    .st-key-landing_center {
       width: 320px !important;
       max-width: 320px !important;
       min-width: 320px !important;
       margin-left: auto !important;
       margin-right: auto !important;
    }

    [data-testid="stSidebar"] .stButton > button {
       background: transparent !important;
       border: none !important;
       box-shadow: none !important;

       color: #172033 !important;
       text-align: left !important;

       justify-content: flex-start !important;

       margin-left: 20px !important;
       width: calc(100% - 8px) !important;

       padding: 14px 14px !important;
       border-radius: 10px !important;

       font-weight: 500 !important;
    }

    [data-testid="stSidebar"] .stButton > button:hover {
       background-color: #F6E7C9 !important;
       color: #172033 !important;
    }

    [data-testid="stSidebar"] .stButton > button {
       font-size: 17px !important;
       padding-top: 7px !important;
       padding-bottom: 7px !important;
    }

    [data-testid="stSidebar"] .st-key-btn_importar_pdf button {
       padding-top: 22px !important;
       padding-bottom: 22px !important;
    }

    [data-testid="stSidebarContent"] {
       margin-top: -3rem !important;
       height:calc(100% + 3rem) !important;
    }

    .st-key-btn_voltar_conta button::before {
       content: "";
       width: 26px;
       height: 26px;
       display: inline-block;
       background: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23B87928%22%20stroke-width%3D%221.7%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M9%205%203%2011l6%206M3%2011h12a6%206%200%200%201%206%206v2%22%2F%3E%3C%2Fsvg%3E") center / contain no-repeat;
       margin-right: 10px;
       flex-shrink: 0;
    }


    .st-key-btn_sair button::before {
       content: "";

       width: 32px;
       height: 32px;

       flex-shrink: 0;
       margin-right: 10px;

       background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' fill='none'%3E%3Cpath d='M6 5 H17 V27 H6 Z' stroke='%23B87928' stroke-width='2' stroke-linejoin='round'/%3E%3Cpath d='M14 16 H27' stroke='%23B87928' stroke-width='2.4' stroke-linecap='round'/%3E%3Cpath d='M22 11 L27 16 L22 21' stroke='%23B87928' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");

       background-size: contain;
       background-position: center;
       background-repeat: no-repeat;
}




    .st-key-btn_cadastrar_gasto button,
    .st-key-btn_cadastrar_receita button,
    .st-key-btn_importar_pdf button {
      min-height: 34px !important;
      height: 34px !important;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
      margin-bottom: 10px !important;
    }

    .st-key-btn_cadastrar_gasto button::before {
      content: "-R$";
      width: 34px;
      height: 30px;
      border: 2px solid #B87928;
      border-radius: 15px;

      display: inline-flex;
      align-items: center;
      justify-content: center;

      color: #B87928;
      font-size: 12px;
      font-weight: 700;

      margin-right: 10px;
      flex-shrink: 0;
   }

    .st-key-btn_cadastrar_receita button::before {
      content: "+R$";
      width: 34px;
      height: 30px;
      border: 2px solid #B87928;
      border-radius: 15px;

      display: inline-flex;
      align-items: center;
      justify-content: center;

      color: #B87928;
      font-size: 12px;
      font-weight: 700;

      margin-right: 10px;
      flex-shrink: 0;
   }

    .st-key-btn_importar_pdf button::before {
      content: "⇩";
      width: 32px;
      height: 36px;

      display: inline-flex;
      align-items: center;
      justify-content: center;

      border: 2px solid #B87928;
      border-radius: 3px;

      color: #B87928;
      font-size: 22px;
      font-weight: 700;

      margin-right: 10px;
      flex-shrink: 0;
    }




    .st-key-btn_visualizar_saldo button,
    .st-key-btn_visualizar_historico button,
    .st-key-btn_acompanhar_meta button,
    .st-key-btn_fluxo_caixa button,
    .st-key-btn_visualizar_dashboard button {
      min-height: 48px !important;
      height: 48px !important;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
      margin-bottom: 12px !important;
    }

    [data-testid="stSidebar"] .st-key-btn_visualizar_historico button {
      height: auto !important;
      min-height: 48px !important;
      padding-top: 8px !important;
      padding-bottom: 8px !important;
    }

   .st-key-btn_visualizar_saldo button::before {
    content: "R$";
    width: 30px;
    height: 30px;
    border: 2px solid #B87928;
    border-radius: 50%;

    display: inline-flex;
    align-items: center;
    justify-content: center;

    color: #B87928;
    font-size: 12px;
    font-weight: 700;

    margin-right: 10px;
    flex-shrink: 0;
    }


    .st-key-btn_visualizar_historico button::before {
    content: "↶";
    width: 30px;
    height: 30px;

    display: inline-flex;
    align-items: center;
    justify-content: center;

    color: #B87928;
    font-size: 30px;
    font-weight: 500;
    line-height: 1;

    margin-right: 10px;
    flex-shrink: 0;
    }


    .st-key-btn_acompanhar_meta button::before {
    content: "";
    width: 30px;
    height: 30px;

    border: 2px solid #B87928;
    border-radius: 50%;

    background:
        radial-gradient(
            circle,
            #B87928 0 3px,
            transparent 4px 8px,
            #B87928 9px 10px,
            transparent 11px
        );

    margin-right: 10px;
    flex-shrink: 0;
    }


    .st-key-btn_fluxo_caixa button::before {
      content: "";
      display: inline-block;
      width: 30px;
      height: 30px;
      margin-right: 10px;
      flex-shrink: 0;
      background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2032%2032%22%20fill%3D%22none%22%20stroke%3D%22%23B87928%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Crect%20x%3D%223%22%20y%3D%2210%22%20width%3D%2226%22%20height%3D%2212%22%20rx%3D%222%22%2F%3E%3Ccircle%20cx%3D%2216%22%20cy%3D%2216%22%20r%3D%223%22%2F%3E%3Cpath%20d%3D%22M5%205H26M23%202l3%203-3%203M27%2027H6M9%2024l-3%203%203%203%22%2F%3E%3C%2Fsvg%3E");
      background-size: contain;
      background-position: center;
      background-repeat: no-repeat;
    }

    .st-key-btn_visualizar_dashboard button::before {
    content: "";
    width: 30px;
    height: 30px;

    background: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22%23B87928%22%3E%3Crect%20x%3D%222%22%20y%3D%222%22%20width%3D%228%22%20height%3D%228%22%20rx%3D%221%22%2F%3E%3Crect%20x%3D%2214%22%20y%3D%222%22%20width%3D%228%22%20height%3D%228%22%20rx%3D%221%22%2F%3E%3Crect%20x%3D%222%22%20y%3D%2214%22%20width%3D%228%22%20height%3D%228%22%20rx%3D%221%22%2F%3E%3Crect%20x%3D%2214%22%20y%3D%2214%22%20width%3D%228%22%20height%3D%228%22%20rx%3D%221%22%2F%3E%3C%2Fsvg%3E") center / contain no-repeat;

    border-radius: 2px;
    margin-right: 10px;
    flex-shrink: 0;
    }




    .st-key-btn_orcamento button,
    .st-key-btn_recorrencias button,
    .st-key-btn_planejamento_mensal button,
    .st-key-btn_planejamento_anual button,
    .st-key-btn_simulador button {
      min-height: 48px !important;
      height: 48px !important;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
   }

    .st-key-btn_orcamento button::before {
      content: "R$";
      width: 38px;
      height: 28px;

      display: inline-flex;
      align-items: center;
      justify-content: center;

      border: 2px solid #B87928;
      border-radius: 4px;

      color: #B87928;
      font-size: 12px;
      font-weight: 700;

      margin-right: 10px;
      flex-shrink: 0;
    }


    .st-key-btn_recorrencias button::before {
      content: "↻";
      width: 38px;
      height: 32px;

      display: inline-flex;
      align-items: center;
      justify-content: center;

      color: #B87928;
      font-size: 34px;
      font-weight: 400;

      margin-right: 10px;
      flex-shrink: 0;
    }


    .st-key-btn_planejamento_mensal button::before {
      content: "";
      width: 26px;
      height: 26px;
      display: inline-block;
      background: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23B87928%22%20stroke-width%3D%221.7%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Crect%20x%3D%223%22%20y%3D%225%22%20width%3D%2218%22%20height%3D%2216%22%20rx%3D%222%22%2F%3E%3Cpath%20d%3D%22M7%203v4M17%203v4M3%2010h18%22%2F%3E%3Cg%20fill%3D%22%23B87928%22%20stroke%3D%22none%22%3E%3Crect%20x%3D%226%22%20y%3D%2213%22%20width%3D%222.5%22%20height%3D%222.5%22%20rx%3D%22.4%22%2F%3E%3Crect%20x%3D%2210.75%22%20y%3D%2213%22%20width%3D%222.5%22%20height%3D%222.5%22%20rx%3D%22.4%22%2F%3E%3Crect%20x%3D%2215.5%22%20y%3D%2213%22%20width%3D%222.5%22%20height%3D%222.5%22%20rx%3D%22.4%22%2F%3E%3Crect%20x%3D%226%22%20y%3D%2217%22%20width%3D%222.5%22%20height%3D%222.5%22%20rx%3D%22.4%22%2F%3E%3Crect%20x%3D%2210.75%22%20y%3D%2217%22%20width%3D%222.5%22%20height%3D%222.5%22%20rx%3D%22.4%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E") center / contain no-repeat;
      margin-right: 10px;
      flex-shrink: 0;
    }


    .st-key-btn_planejamento_anual button::before {
      content: "";
      width: 26px;
      height: 26px;
      display: inline-block;
      background: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23B87928%22%20stroke-width%3D%221.7%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Crect%20x%3D%223%22%20y%3D%223%22%20width%3D%2218%22%20height%3D%2218%22%20rx%3D%222%22%2F%3E%3Cpath%20d%3D%22M12%203v18M3%2012h18M6%206h3M15%206h3M6%2015h3M15%2015h3%22%2F%3E%3C%2Fsvg%3E") center / contain no-repeat;
      margin-right: 10px;
      flex-shrink: 0;
    }

    .st-key-btn_simulador_financeiro button::before {
      content: "%";
      width: 32px;
      height: 32px;

      display: inline-flex;
      align-items: center;
      justify-content: center;

      border: 2px solid #B87928;
      border-radius: 50%;

      color: #B87928;
      font-size: 17px;
      font-weight: 700;

      margin-right: 10px;
      flex-shrink: 0;
    }




    .st-key-btn_inteligencia_financeira button,
    .st-key-btn_relatorio_mensal button {
      min-height: 48px !important;
      height: 48px !important;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
      margin-bottom: 4px !important;
    }

    .st-key-btn_inteligencia_financeira button::before {
      content: "";

      width: 34px;
      height: 30px;

      flex-shrink: 0;
      margin-right: 10px;

      background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23B87928%22%20stroke-width%3D%221.7%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M12%206a3%203%200%200%200-5.8-1A4%204%200%200%200%203.5%2011a4%204%200%200%200%201%207A3.5%203.5%200%200%200%2012%2019V6Zm0%200a3%203%200%200%201%205.8-1%204%204%200%200%201%202.7%206%204%204%200%200%201-1%207A3.5%203.5%200%200%201%2012%2019%22%2F%3E%3Cpath%20d%3D%22M7%205v3l2%202M3.5%2011H7M4.5%2018l3-3v-2M17%205v3l-2%202M20.5%2011H17M19.5%2018l-3-3v-2%22%2F%3E%3C%2Fsvg%3E");

      background-size: contain;
      background-position: center;
      background-repeat: no-repeat;
    }


    .st-key-btn_relatorio_mensal button::before {
      content: "";

      width: 34px;
      height: 32px;

      flex-shrink: 0;
      margin-right: 10px;

      background-image: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23B87928%22%20stroke-width%3D%221.7%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Crect%20x%3D%223%22%20y%3D%225%22%20width%3D%2218%22%20height%3D%2216%22%20rx%3D%222%22%2F%3E%3Cpath%20d%3D%22M7%203v4M17%203v4M3%2010h18M7%2014h3M7%2017h3M14%2016l2%202%203-4%22%2F%3E%3C%2Fsvg%3E");

      background-size: contain;
      background-position: center;
      background-repeat: no-repeat;
    }


    .st-key-btn_configuracoes button::before {
      content: "";

      width: 32px;
      height: 32px;

      flex-shrink: 0;
      margin-right: 10px;

      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' fill='none'%3E%3Ccircle cx='16' cy='16' r='4' stroke='%23B87928' stroke-width='2'/%3E%3Cpath d='M16 4 V8 M16 24 V28 M4 16 H8 M24 16 H28 M7.5 7.5 L10.5 10.5 M21.5 21.5 L24.5 24.5 M24.5 7.5 L21.5 10.5 M10.5 21.5 L7.5 24.5' stroke='%23B87928' stroke-width='2' stroke-linecap='round'/%3E%3Ccircle cx='16' cy='16' r='9' stroke='%23B87928' stroke-width='2'/%3E%3C/svg%3E");

      background-size: contain;
      background-position: center;
      background-repeat: no-repeat;
    }


    .st-key-btn_conta_demo button::before {
    content: "";

      width: 32px;
      height: 32px;

      flex-shrink: 0;
      margin-right: 10px;

      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' fill='none'%3E%3Ccircle cx='16' cy='16' r='12' stroke='%23B87928' stroke-width='2'/%3E%3Cpath d='M19.5 12.5 L17 17 L12.5 19.5 L15 15 Z' stroke='%23B87928' stroke-width='2' stroke-linejoin='round'/%3E%3C/svg%3E");

      background-size: contain;
      background-position: center;
      background-repeat: no-repeat;
    }




    .st-key-btn_perfil .stButton > button {

      width: 44px !important;
      height: 44px !important;
      min-width: 44px !important;

      padding: 0 !important;

      border-radius: 50% !important;

      background-color: #172033 !important;
      color: white !important;

      border: 1px solid #C9A227 !important;

      font-weight: 600 !important;

      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
   }



    .st-key-btn_alertas .stButton > button {
      width: 44px !important;
      height: 44px !important;
      min-width: 44px !important;

      padding: 0 !important;

      background-color: transparent !important;
      border: none !important;
      box-shadow: none !important;

      display: flex !important;
      align-items: center !important;
      justify-content: center !important;

      position: relative !important;
    }

    .st-key-btn_alertas .stButton > button p {
       font-size: 0 !important;
    }

    .st-key-btn_alertas .stButton > button::before {

      content: "";
      display: block;
      width: 24px;
      height: 24px;

      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23172033' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9'/%3E%3Cpath d='M13.73 21a2 2 0 0 1-3.46 0'/%3E%3C/svg%3E");

      background-size: contain;
      background-position: center;
      background-repeat: no-repeat;
   }

    .st-key-btn_alertas_com_alerta .stButton > button::after {
      content:"";
      display: block;

      position: absolute;
      top: 6px;
      right: 5px;

      width: 8px;
      height: 8px;

      background-color: #F5A623;
      border-radius: 50%;

      border: 1.5px solid white;
   }



    .st-key-menu_configuracoes .stButton > button,
    .st-key-menu_seguranca .stButton > button,
    .st-key-menu_sair .stButton > button {
         background: transparent !important;
         border: none !important;
         box-shadow: none !important;

         width: 100% !important;
         justify-content: flex-start !important;
         text-align: left !important;

         padding: 3px 20px !important;
         min-height: 30px !important;
         border-radius: 6px !important;

         color: #172033 !important;
         font-weight: 500 !important;
       }

    .st-key-menu_configuracoes .stButton > button:hover,
    .st-key-menu_seguranca .stButton > button:hover,
    .st-key-menu_sair .stButton > button:hover {
      background-color: #F5F6F8 !important;
    }


    .st-key-menu_conta_box {
      background-color: #FFFFFF !important;
      margin-top: 0 !important;
      transform: none !important;
    }

    .st-key-menu_conta_box [data-testid="stVerticalBlock"] {
      gap: 0.05rem !important;
    }

    .st-key-menu_conta_box hr {
      margin: 2px 0 !important;
    }

    .st-key-menu_conta_box {
      padding-bottom: 4px !important;
    }


    .st-key-menu_conta_box {
    position: relative !important;
    }

    .st-key-menu_conta_box::before {
      content: "";
      position: absolute;

      top: -10px;
      right: 22px;

      width: 0;
      height: 0;

      border-left: 10px solid transparent;
      border-right: 10px solid transparent;
      border-bottom: 10px solid #D9DEE7;

      z-index: 999;
    }

    .st-key-menu_conta_box::after {
      content: "";
      position: absolute;

      top: -8px;
      right: 23px;

      width: 0;
      height: 0;

      border-left: 9px solid transparent;
      border-right: 9px solid transparent;
      border-bottom: 9px solid white;

      z-index: 1000;
   }

    .st-key-menu_sair .stButton > button::before {
      content: "";

      width: 18px;
      height: 18px;

      flex-shrink: 0;
      margin-right: 7px;

      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' fill='none'%3E%3Cpath d='M6 5 H17 V27 H6 Z' stroke='%23B87928' stroke-width='2' stroke-linejoin='round'/%3E%3Cpath d='M14 16 H27' stroke='%23B87928' stroke-width='2.4' stroke-linecap='round'/%3E%3Cpath d='M22 11 L27 16 L22 21' stroke='%23B87928' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");

      background-size: contain;
      background-position: center;
      background-repeat: no-repeat;
   }


    .st-key-menu_configuracoes .stButton > button::before {
      content: "";

      width: 18px;
      height: 18px;

      flex-shrink: 0;
      margin-right: 7px;

      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' fill='none'%3E%3Ccircle cx='16' cy='16' r='4' stroke='%23B87928' stroke-width='2'/%3E%3Cpath d='M16 4 V8 M16 24 V28 M4 16 H8 M24 16 H28 M7.5 7.5 L10.5 10.5 M21.5 21.5 L24.5 24.5 M24.5 7.5 L21.5 10.5 M10.5 21.5 L7.5 24.5' stroke='%23B87928' stroke-width='2' stroke-linecap='round'/%3E%3Ccircle cx='16' cy='16' r='9' stroke='%23B87928' stroke-width='2'/%3E%3C/svg%3E");

      background-size: contain;
      background-position: center;
      background-repeat: no-repeat;
   }


    .st-key-menu_seguranca .stButton > button::before {
      content: "";
      width: 18px;
      height: 18px;
      margin-right: 7px;
      flex-shrink: 0;

      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23C6A15B' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='10' width='16' height='11' rx='2'/%3E%3Cpath d='M8 10V7a4 4 0 0 1 8 0v3'/%3E%3C/svg%3E");
      background-size: contain;
      background-position: center;
      background-repeat: no-repeat;
    }


    .topo-menu-trixter {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;

      height: 72px;

      background-color: #FFFFFF;

      border-bottom: 1px solid #EEF0F3;

      z-index: 0;
   }


    .st-key-topo_menu {
      background: #FFFFFF !important;

      border-bottom: 1px solid #E8E8E8 !important;

      padding: 8px 18px 10px 18px !important;

      margin-left: -18px !important;
      margin-right: -18px !important;
   }



    .st-key-voltar_menu_principal {
         opacity: 1 !important;
         visibility: visible !important;
   }


    .st-key-voltar_menu_principal,
    .st-key-voltar_menu_principal * {
         transition: none !important;
         animation: none !important;
   }




   .st-key-menu_alertas_box {
      background-color: #FFFFFF !important;
      max-width: 195px !important;
      height: fit-content !important;
      min-height: 0 !important;
      flex: 0 0 auto !important;
      padding: 4px 6px !important;
      visibility: visible !important;
      position: relative !important;
      margin-top: 0 !important;
      transform: none !important;
   }

   .st-key-menu_alertas_box,
   .st-key-menu_alertas_box [data-testid="stVerticalBlock"] {
     gap: 0rem !important;
   }

   /* Elementos antigos do rerun nao devem aparecer dentro das notificacoes. */
   .st-key-menu_alertas_box [data-stale="true"] {
      display: none !important;
   }

   .st-key-menu_alertas_box [data-testid="stAlert"] {
     background: transparent !important;
     border: none !important;
     padding: 0 !important;
   }

   /* Quebra de texto restrita ao conteudo das notificacoes. */
   .st-key-menu_alertas_box [data-testid="stAlert"] [data-testid="stMarkdownContainer"] {
      min-width: 0 !important;
      max-width: 100% !important;
      white-space: normal !important;
      overflow-wrap: anywhere !important;
      word-break: normal !important;
   }

   .st-key-menu_alertas_box [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
      white-space: normal !important;
      overflow-wrap: anywhere !important;
      line-height: 1.5 !important;
   }

   .st-key-menu_alertas_box [data-testid="stAlert"] svg {
     display: none !important;
   }




   .st-key-btn_ver_todos_alertas button {
      background: transparent !important;
      border: none !important;
      box-shadow: none !important;
      padding: 0 !important;
      min-height: 0 !important;
   }

   .st-key-btn_ver_todos_alertas button p {
      color: #8B6F2F !important;
   }


   .st-key-btn_ver_todos_alertas button:hover {
      background: transparent !important;
      border: none !important;
   }

   .st-key-btn_ver_todos_alertas button:hover p {
      text-decoration: underline;
   }

   .st-key-menu_alertas_box [data-testid="stAlert"] > div {
      background-color: transparent !important;
   }

   .st-key-menu_alertas_box [data-testid="stAlert"] div {
      background: transparent !important;
   }

   .st-key-menu_alertas_box [data-testid="stAlert"] * {
      color: #000000 !important;
   }


   .st-key-menu_alertas_box::before {
      content: "";
      position: absolute;
      top: -9px;
      right: 22px;

      width: 16px;
      height: 16px;

      background: white;
      border-left: 1px solid #d9d9d9;
      border-top: 1px solid #d9d9d9;

      transform: rotate(45deg);
      z-index: 2;
   }"""

ESTILO_MENUS = """\
.st-key-cabecalho_menu .st-key-menu_conta_box,
.st-key-cabecalho_menu .st-key-menu_conta_box *,
.st-key-cabecalho_menu .st-key-menu_configuracoes,
.st-key-cabecalho_menu .st-key-menu_configuracoes *,
.st-key-cabecalho_menu .st-key-menu_seguranca,
.st-key-cabecalho_menu .st-key-menu_seguranca *,
.st-key-cabecalho_menu .st-key-menu_sair,
.st-key-cabecalho_menu .st-key-menu_sair * {{
    visibility: {menu_conta_visibilidade} !important;
    pointer-events: {menu_conta_interacao} !important;
}}
.st-key-cabecalho_menu .st-key-menu_alertas_box,
.st-key-cabecalho_menu .st-key-menu_alertas_box * {{
    visibility: {menu_alertas_visibilidade} !important;
    pointer-events: {menu_alertas_interacao} !important;
}}"""

ESTILO_CORTINA_TROCA = """\
.cortina-troca-conta {
    position: fixed;
    inset: 0;
    background: #F7F8FA;
    z-index: 1000000;
}"""

ESTILO_ESCONDER_MIOLO = """\
[data-testid="stMain"],
[data-testid="stMain"] * {
    display: none !important;
    visibility: hidden !important;
}"""

ESTILO_LOGADO = """\
/* O rerun marca a tela antiga como stale e baixa a opacidade para 0,33. */
[data-stale="true"] {
    opacity: 1 !important;
    transition: none !important;
    animation: none !important;
}

/* Estas cores saem no início da sessão, fora do container que Configurações
   e Segurança esvaziam no clique. Assim o fundo e a sidebar não voltam
   ao tema anterior enquanto a tela nova espera o banco. */
[data-testid="stAppViewContainer"] {
    background-color: #F7F8FA !important;
}

[data-testid="stHeader"] {
    background: transparent !important;
}

[data-testid="stSidebar"] > div:first-child {
    background-color: #FAF7EE !important;
}

[data-testid="stSidebar"] {
    border-right: 1px solid #E3E7ED !important;
}

.block-container {
    padding-top: 2rem !important;
}"""

ESTILO_FUNDO = """\
[data-testid="stAppViewContainer"] {{
   background-image: url("data:image/png;base64,{img_fundo}") !important;
   background-size: cover !important;
   background-position: center center !important;
   background-repeat: no-repeat !important;
   background-attachment: scroll !important;
}}"""

ESTILO_CADASTRO = """\
[data-testid="stAppViewContainer"] {
    background-color: rgba(255, 255, 255, 0.72) !important;
    background-blend-mode: lighten !important;
}"""

ESTILO_SEM_SESSAO = """\
[data-testid="stHeader"] {
   display: none !important;
}

[data-testid="stToolBar"] {
   display: none !important;
}"""

ESTILO_LANDING = """\
[data-testid="stSidebar"] {
   display: none !important;
}"""

ESTILO_OCULTAR_NAVEGACAO = """\
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"] {display:none !important;}"""

ESTILO_ONBOARDING = """\
.onboarding-card {
   background: rgba(255, 255, 255, 0.82);
   border: 1px solid #E2D3AE;
   border-radius: 14px;
   padding: 22px;
   min-height: 145px;
   box-shadow: 0 3px 12px rgba(0, 0, 0, 0.04);
}

.onboarding-card-title {
   font-size: 18px;
   font-weight: 700;
   color: #181818;
   margin-bottom: 10px;
}

.onboarding-card-text {
   font-size: 14px;
   color: #5F6470;
   line-height: 1.6;
}"""

ESTILO_BOTOES_MENU = """\
div[data-testid="stButton"]:has(button[kind="secondary"]) {
}

button[kind="secondary"]:has(p) {
}"""

ESTILO_ALERTA = """\
.st-key-btn_alertas .stButton > button::after {
      content: "";
      display: block;
      position: absolute;
      top: 6px;
      right: 5px;
      width: 8px;
      height: 8px;
      background-color: #F5A623;
      border-radius: 50%;
      border: 1.5px solid white;
}"""

ESTILO_SEGURANCA = """\
.titulo-seguranca {
   display: flex;
   align-items: center;
   gap: 8px;
   font-size: 24px;
   font-weight: 600;
}

.icone-seguranca {
   display: inline-block;
   width: 24px;
   height: 24px;

   background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23C6A15B' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='10' width='16' height='11' rx='2'/%3E%3Cpath d='M8 10V7a4 4 0 0 1 8 0v3'/%3E%3C/svg%3E");
   background-size: contain;
   background-position: center;
   background-repeat: no-repeat;
}"""

ESTILO_AUTENTICADO = """\
/* Durante o rerun o Streamlit marca a tela antiga como stale e baixa a opacidade para 0,33. */
[data-stale="true"] {
    opacity: 1 !important;
    transition: none !important;
    animation: none !important;
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"] {background-color:#F7F8FA;}
[data-testid="stSidebar"] > div:first-child {background-color:#FAF7EE;}
[data-testid="stSidebar"] {border-right:1px solid #E3E7ED;}
[data-testid="stSidebar"] .stButton > button {
    height:auto !important; min-height:44px !important;
    margin:0 !important; width:100% !important;
    padding:8px 12px !important; color:#172033 !important;
}
[data-testid="stSidebar"] .stButton > button::before {
    width:26px !important; height:26px !important; flex-shrink:0;
    background-size:contain !important; margin-right:10px !important;
}
[data-testid="stSidebar"] .stButton > button:hover {background:#F1E8D6 !important;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:10px;}
[data-testid="stSidebar"] .titulo-secao-sidebar {
    margin:0 !important;
    padding-top:16px;
    padding-bottom:10px;
}
[data-testid="stSidebar"] .titulo-secao-sidebar > :first-child {
    width:32px !important;
    height:32px !important;
    flex:0 0 32px !important;
}
[data-testid="stSidebar"] .titulo-secao-sidebar svg {
    width:32px !important;
    height:32px !important;
}
[data-testid="stSidebar"] .titulo-secao-sidebar > div:first-child:has(> span) {
    justify-content:center;
}
[data-testid="stSidebar"] .titulo-secao-sidebar > div:first-child > span {
    width:6px !important;
}
[data-testid="stSidebar"] .titulo-secao-sidebar > div:first-child > span:nth-child(1) {height:12px !important;}
[data-testid="stSidebar"] .titulo-secao-sidebar > div:first-child > span:nth-child(2) {height:21px !important;}
[data-testid="stSidebar"] .titulo-secao-sidebar > div:first-child > span:nth-child(3) {height:30px !important;}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
    background:#172033 !important; border-color:#172033 !important; color:#FFFFFF !important;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background:#283852 !important; border-color:#283852 !important; color:#FFFFFF !important;
}
.st-key-resumo_inicio [data-testid="stMetric"] {
    background:#FFFFFF; border:1px solid #E3E7ED; border-top:3px solid #B87928;
    border-radius:14px; padding:20px; box-shadow:0 3px 12px rgba(23,32,51,0.04);
}
.st-key-resumo_inicio [data-testid="stMetricValue"] {font-size:clamp(1.3rem,2.3vw,2rem);color:#172033;}
.st-key-resumo_inicio [data-testid="stMetricLabel"] {color:#526077;}
.st-key-resumo_inicio {margin-top:80px;}
.trixter-saudacao {font-size:clamp(26px,3vw,36px);font-weight:700;color:#172033;margin:20px 0 8px;line-height:1.2;}
/* Dropdowns ancorados nas colunas dos botões, fora do fluxo do resumo. */
[data-testid="stColumn"]:has(.st-key-ancora_menu_conta),
[data-testid="stColumn"]:has(.st-key-ancora_menu_alertas) {
    position:relative !important;
    overflow:visible !important;
}
.st-key-ancora_menu_conta, .st-key-ancora_menu_alertas {
    position:absolute !important; top:56px; right:calc(100% - 44px);
    width:210px !important; max-width:calc(100vw - 32px) !important;
    height:auto !important; min-height:0 !important;
    z-index:1001; overflow:visible;
}
.st-key-ancora_menu_alertas {width:195px !important;}
.st-key-ancora_menu_conta .st-key-menu_conta_box {
    padding:12px 12px !important; width:100% !important;
    gap:6px !important;
    box-shadow:0 6px 20px rgba(23,32,51,0.10);
}
.st-key-ancora_menu_conta .st-key-menu_conta_box [data-testid="stVerticalBlock"] {
    gap:6px !important;
}
.st-key-ancora_menu_conta .st-key-menu_conta_box .stButton > button {
    min-height:40px !important; padding:6px 8px !important;
}
.st-key-ancora_menu_conta .st-key-menu_conta_box [data-testid="stElementContainer"]:has(hr) {
    margin:0 !important; padding:0 !important;
}
.st-key-ancora_menu_conta .st-key-menu_conta_box hr {
    margin:4px 0 !important;
}
.dados-menu-conta {padding-bottom:8px;border-bottom:1px solid #E3E7ED;margin-bottom:4px;}
.nome-menu-conta {font-size:14px;font-weight:600;line-height:1.35;color:#172033;}
.email-menu-conta,.tipo-menu-conta {font-size:12px;line-height:1.4;color:#657085;overflow-wrap:anywhere;}
.email-menu-conta {margin-top:4px;}
.st-key-ancora_menu_conta .st-key-menu_conta_box::before {right:12px;}
.st-key-ancora_menu_conta .st-key-menu_conta_box::after {right:13px;}
.st-key-ancora_menu_alertas .st-key-menu_alertas_box::before {right:14px;}
[data-testid="stSidebar"] button:focus-visible {outline:2px solid #172033 !important;outline-offset:2px;}"""

def publicar_menus(conta_aberta, alertas_abertos):
    publicar(ESTILO_MENUS.format(
        menu_conta_visibilidade="visible" if conta_aberta else "hidden",
        menu_conta_interacao="auto" if conta_aberta else "none",
        menu_alertas_visibilidade="visible" if alertas_abertos else "hidden",
        menu_alertas_interacao="auto" if alertas_abertos else "none",
    ))


def publicar_fundo(seletor='[data-testid="stAppViewContainer"]'):
    imagem = base64.b64encode(Path("assets/trixter_background.png").read_bytes()).decode()
    publicar(ESTILO_FUNDO.format(img_fundo=imagem).replace(
        '[data-testid="stAppViewContainer"]', seletor,
    ))


def publicar_fundo_documentos():
    # Reutiliza imagem e suavizacao do cadastro, somente enquanto os documentos existem.
    seletor = '[data-testid="stAppViewContainer"]:has(.st-key-documentos_legais)'
    publicar_fundo(seletor)
    publicar(ESTILO_CADASTRO.replace('[data-testid="stAppViewContainer"]', seletor))


def publicar_area_autenticada(tela, paginas):
    publicar(ESTILO_AUTENTICADO)
    seletores = ",\n".join(
        f'[data-testid="stSidebar"] .st-key-{chave} .stButton > button'
        for chave in (*paginas.values(), "btn_conta_demo", "btn_voltar_conta")
    )
    publicar(
        f"{seletores} {{\n"
        "        margin-left:12px !important;\n"
        "        width:calc(100% - 12px) !important;\n"
        "    }"
    )
    chave = paginas.get(tela)
    if chave:
        publicar(
            f'[data-testid="stSidebar"] .st-key-{chave} button {{\n'
            "            background:#EEE4D1 !important; box-shadow:inset 3px 0 #B87928 !important;\n"
            "        }\n"
            f'        [data-testid="stSidebar"] .st-key-{chave} button p {{font-weight:700 !important;}}'
        )
