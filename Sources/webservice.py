import os
import requests
from xml.dom.minidom import parseString
import pytz
import dateutil.parser
import urllib.request

class FITS_Web_Serivce():
    def __init__(self):
        self.url = "https://service-t.fabrinet.co.th/FBNFITSService/FBNFITSServices.svc?wsdl"
        self.project_id = "729"
        self.user_name = "tech_ws"
        self.user_password = "kG7m@691"
        
    def getStatusURL(self):
        try:
            page = urllib.request.urlopen(self.url)
            if page.getcode() == 200:
                status = "OK"
            else:
                status = "NOK"
        except:
            status = "ERROR"
        return status

    def check_valid_data(a: str):
        origin = a
        if a.count('.') > 0:
            s = a  # buffer only.
            a = s[:s.rfind('.') - len(s)]
        if a == "99999" or a == "9999":
            origin = "-"
        if a == "-9999999" or a == "9999999":
            origin = "ERROR"
        return origin

    def FIT_Handshake(self, sn: str, station_no: str, partno: str):
        xml_soap = """<?xml version='1.0'?>
        <x:Envelope xmlns:x="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem='http://tempuri.org/'>
            <x:Header/>
            <x:Body>
                <tem:fn_Handshake>
                    <tem:project_id>{pro_id}</tem:project_id>
                    <tem:user_name>{user}</tem:user_name>
                    <tem:user_password>{pass}</tem:user_password>
                    <tem:model>{PN}</tem:model>
                    <tem:operation>{station}</tem:operation>
                    <tem:revision>2.4</tem:revision>
                    <tem:serial>{SN}</tem:serial>
                </tem:fn_Handshake>
            </x:Body>
        </x:Envelope>"""
        headers = {
            'Content-Type': 'text/xml; charset=UTF-8', 'SOAPAction': '"http://tempuri.org/IFBNFITSServices/fn_Handshake"'
        }
        xml_soap = xml_soap.replace("{pro_id}", self.project_id).replace("{user}", self.user_name).replace("{pass}",
                                    self.user_password).replace("{PN}", partno).replace("{SN}", sn).replace("{station}", station_no)
        response = requests.request("POST", self.url, headers=headers, data=xml_soap)
        FIT_result = FITS_Web_Serivce.query_fit_ressult(response.text)
        if FIT_result.upper() == "TRUE" or FIT_result.upper() == "OK":
            return True
        else:
            return FITS_Web_Serivce.query_fit_response(response.text)

    def FIT_Query(self, sn: str, station_no: str, partno: str, parameter: str):
        xml_soap = """<?xml version='1.0'?>
        <x:Envelope xmlns:x="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem='http://tempuri.org/'>
            <x:Header/>
            <x:Body>
                <tem:fn_Query>
                <tem:project_id>{pro_id}</tem:project_id>
                <tem:user_name>{user}</tem:user_name>
                <tem:user_password>{pass}</tem:user_password>
                <tem:model>{PN}</tem:model>
                <tem:operation>{station}</tem:operation>
                <tem:revision>2.4</tem:revision>
                <tem:serial>{SN}</tem:serial>
                <tem:parameters>{parameter}</tem:parameters>
                <tem:fsp>,</tem:fsp>
            </tem:fn_Query>
            </x:Body>
        </x:Envelope>"""
        headers = {
            'Content-Type': 'text/xml; charset=UTF-8', 'SOAPAction': '"http://tempuri.org/IFBNFITSServices/fn_Query"'
        }
        xml_soap = xml_soap.replace("{pro_id}", self.project_id).replace("{user}", self.user_name).replace("{pass}",
                                    self.user_password).replace("{PN}", partno).replace("{SN}", sn).replace("{station}",
                                    station_no).replace("{parameter}", parameter)
        # print(xml_soap)
        response = requests.request("POST", self.url, headers=headers, data=xml_soap)
        # print(response.text)
        aResult = FITS_Web_Serivce.query_fit_response(response.text)
        aResult = str(aResult).split(':', 1)[1]
        return aResult

    def FIT_IN260_Log(self, sn: str, station_no: str, partno: str, Param: str, value: str):
        xml_fn_log = """<?xml version='1.0'?>
            <x:Envelope
                xmlns:x="http://schemas.xmlsoap.org/soap/envelope/"
                xmlns:tem="http://tempuri.org/">
                <x:Header/>
                <x:Body>
                    <tem:fn_Log>
                        <tem:project_id>{pro_id}</tem:project_id>
                        <tem:user_name>{user}</tem:user_name>
                        <tem:user_password>{pass}</tem:user_password>
                        <tem:model>{PN}</tem:model>
                        <tem:operation>{station}</tem:operation>
                        <tem:revision>2.4</tem:revision>
                        <tem:parameters>{FIT_Param}</tem:parameters>
                        <tem:values>{result_value}</tem:values>
                        <tem:fsp>,</tem:fsp>
                    </tem:fn_Log>
                </x:Body>
            </x:Envelope>"""
            
        headers_fn_log = {
            'Content-Type': 'text/xml; charset=UTF-8', 'SOAPAction': '"http://tempuri.org/IFBNFITSServices/fn_Log"'
        }
        xml_soap = xml_fn_log.replace("{pro_id}", self.project_id).replace("{user}", self.user_name).replace("{pass}",
                                    self.user_password).replace("{PN}", partno).replace("{SN}", sn).replace("{station}",
                                    station_no).replace("{FIT_Param}", Param).replace("{result_value}", value)  
        print(xml_soap)                       
        response = requests.request("POST", self.url, headers=headers_fn_log, data=xml_soap)
        FIT_result = FITS_Web_Serivce.query_fit_ressult(response.text)
        print(FIT_result)
        if FIT_result.upper() == "TRUE" or FIT_result.upper() == "OK":
            return FIT_result
        else:
            raise Exception("FIT ERROR = " + FITS_Web_Serivce.query_fit_response(response.text))
        
    def FIT_IN160_Log(self, station_no: str, partno: str, Param: str, value: str):
            xml_fn_log = """<?xml version='1.0'?>
                <x:Envelope
                    xmlns:x="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:tem="http://tempuri.org/">
                    <x:Header/>
                    <x:Body>
                        <tem:fn_Log>
                            <tem:project_id>{pro_id}</tem:project_id>
                            <tem:user_name>{user}</tem:user_name>
                            <tem:user_password>{pass}</tem:user_password>
                            <tem:model>{PN}</tem:model>
                            <tem:operation>{station}</tem:operation>
                            <tem:revision>2.4</tem:revision>
                            <tem:parameters>{FIT_Param}</tem:parameters>
                            <tem:values>{result_value}</tem:values>
                            <tem:fsp>,</tem:fsp>
                        </tem:fn_Log>
                    </x:Body>
                </x:Envelope>"""
                
            headers_fn_log = {
                'Content-Type': 'text/xml; charset=UTF-8', 'SOAPAction': '"http://tempuri.org/IFBNFITSServices/fn_Log"'
            }
            xml_soap = xml_fn_log.replace("{pro_id}", self.project_id).replace("{user}", self.user_name).replace("{pass}",
                                        self.user_password).replace("{PN}", partno).replace("{station}",
                                        station_no).replace("{FIT_Param}", Param).replace("{result_value}", value)  
            print(xml_soap)                       
            response = requests.request("POST", self.url, headers=headers_fn_log, data=xml_soap)
            FIT_result = FITS_Web_Serivce.query_fit_ressult(response.text)
            # print(FIT_result)
            if FIT_result.upper() == "TRUE" or FIT_result.upper() == "OK":
                return FIT_result
            else:
                raise Exception("FIT ERROR = " + FITS_Web_Serivce.query_fit_response(response.text))
        
    def query_fit_response(xml_str: str):
        dom = parseString(xml_str)
        a = dom.getElementsByTagName("a:Message")
        return str(a[0].firstChild.nodeValue)

    def query_fit_ressult(xml_str: str):
        dom = parseString(xml_str)
        a = dom.getElementsByTagName("a:Result")
        return str(a[0].firstChild.nodeValue)

    def test(inp: float):
        print(str(inp))

    def convert_fit_time_to_UTC(time_str: str):  # , input_format: str):
        local = pytz.timezone("Asia/Bangkok")
        if time_str.count(':') > 2:
            s = time_str  # buffer only.
            time_str = s[:s.rfind(':') - len(s)]
        naive = dateutil.parser.parse(time_str)  # datetime.strptime(time_str, input_format)
        local_dt = local.localize(naive, is_dst=None)
        utc_dt = local_dt.astimezone(pytz.utc)
        # t = datetime.datetime.now()
        # hour_now = t.hour * 10000
        # min_now = t.minute * 100
        # second_now = t.second
        # offset_t = hour_now + min_now + second_now
        # utc_dt = utc_dt + datetime.timedelta(microseconds=offset_t)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# FITs = FITS_Web_Serivce()
# fn_handcheck = FITs.FIT_Handshake("CIN252400003", "IN360", "*")
# print(fn_handcheck)
# fn_query = FITs.FIT_Query("CIN252400003", "IN360", "*", "Part_Number")
# print(fn_query)
# if fn_handcheck == True:
#     log = FITs.FIT_IN160_Log(station_no, partno, Param, value)
#     print(log)