from webservice import FITS_Web_Serivce

FITsAPI = FITS_Web_Serivce()
query = FITsAPI.FIT_Query("CIN252400003", "IN010", "Main line", "Part_Number")
print(query)