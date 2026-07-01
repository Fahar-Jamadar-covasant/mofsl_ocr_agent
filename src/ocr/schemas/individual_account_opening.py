"""
Pydantic schema for MOFSL Individual Account Opening extraction.

Structured into logical sections matching the document layout:
KYC, Personal, Identity, Address, Contact, Bank, Financial,
Depository, Trading, FATCA, and supporting sections.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class FormDetails(BaseModel):
    form_number: Optional[str] = Field(None, description="Form number printed on the document")
    application_number: Optional[str] = Field(None, description="Application number assigned to this form")
    kyc_number: Optional[str] = Field(None, description="KYC reference number")
    application_type: Optional[str] = Field(None, description="Type of application (e.g. New, Modification)")
    kyc_mode: Optional[str] = Field(None, description="KYC mode (e.g. Normal, eKYC)")
    dp_type: Optional[str] = Field(None, description="Depository participant type (CDSL / NSDL)")
    branch_code: Optional[str] = Field(None, description="Branch code")
    branch_prefix: Optional[str] = Field(None, description="Branch prefix")
    sub_broker_code: Optional[str] = Field(None, description="Sub-broker code")
    ucc_code: Optional[str] = Field(None, description="Unique Client Code (UCC)")
    client_code: Optional[str] = Field(None, description="Client code assigned by the broker")
    dp_internal_reference_number: Optional[str] = Field(None, description="DP internal reference number")
    cdsl_dp_id: Optional[str] = Field(None, description="CDSL DP ID")
    nsdl_dp_id: Optional[str] = Field(None, description="NSDL DP ID")


class PersonalDetails(BaseModel):
    first_name: Optional[str] = Field(None, description="First name of the applicant")
    middle_name: Optional[str] = Field(None, description="Middle name of the applicant")
    last_name: Optional[str] = Field(None, description="Last name of the applicant")
    maiden_name: Optional[str] = Field(None, description="Maiden name if applicable")
    father_spouse_name: Optional[str] = Field(None, description="Father's or spouse's name")
    mother_name: Optional[str] = Field(None, description="Mother's name")
    date_of_birth: Optional[str] = Field(None, description="Date of birth as written in the document")
    gender: Optional[str] = Field(None, description="Gender — use selections as authoritative source")
    marital_status: Optional[str] = Field(None, description="Marital status — use selections as authoritative source")
    nationality: Optional[str] = Field(None, description="Nationality")
    residential_status: Optional[str] = Field(None, description="Residential status (e.g. Resident Individual, NRI)")
    pan_number: Optional[str] = Field(None, description="PAN number — preserve exactly as written")
    photo_present: Optional[bool] = Field(None, description="Whether applicant photo is present on the form")
    signature_present: Optional[bool] = Field(None, description="Whether applicant signature is present — use signatures section")


class IdentityProof(BaseModel):
    proof_type: Optional[str] = Field(None, description="Selected document type for identity/address proof — use selections section")
    identification_number: Optional[str] = Field(None, description="Generic identification number if not captured by a specific field")
    passport_number: Optional[str] = Field(None, description="Passport number if selected")
    passport_expiry_date: Optional[str] = Field(None, description="Passport expiry date — preserve as written")
    driving_license_number: Optional[str] = Field(None, description="Driving license number if selected")
    driving_license_expiry_date: Optional[str] = Field(None, description="Driving license expiry date — preserve as written")
    voter_id_number: Optional[str] = Field(None, description="Voter ID card number if selected")
    aadhaar_number: Optional[str] = Field(None, description="Aadhaar number if present")
    aadhaar_offline_verification: Optional[bool] = Field(None, description="Whether Aadhaar offline verification is selected — use selections section")
    ekyc_authentication: Optional[bool] = Field(None, description="Whether eKYC authentication is selected — use selections section")
    nrega_job_card_number: Optional[str] = Field(None, description="NREGA job card number if selected")
    npr_number: Optional[str] = Field(None, description="NPR letter number if selected")
    other_document_type: Optional[str] = Field(None, description="Other document type if 'Others' is selected")
    other_document_number: Optional[str] = Field(None, description="Other document number if 'Others' is selected")


class Address(BaseModel):
    address_line_1: Optional[str] = Field(None, description="Address line 1")
    address_line_2: Optional[str] = Field(None, description="Address line 2")
    address_line_3: Optional[str] = Field(None, description="Address line 3")
    city: Optional[str] = Field(None, description="City")
    district: Optional[str] = Field(None, description="District")
    state: Optional[str] = Field(None, description="State")
    country: Optional[str] = Field(None, description="Country")
    pin_code: Optional[str] = Field(None, description="PIN / ZIP code — preserve exactly as written")
    address_type: Optional[str] = Field(None, description="Address type (e.g. Residential, Business) — use selections section")


class PermanentAddress(Address):
    same_as_correspondence: Optional[bool] = Field(None, description="Whether permanent address is the same as correspondence address — use selections section")


class ContactDetails(BaseModel):
    email: Optional[str] = Field(None, description="Email address")
    mobile_number: Optional[str] = Field(None, description="Mobile number — preserve exactly as written including country code")
    office_phone: Optional[str] = Field(None, description="Office telephone number")
    residence_phone: Optional[str] = Field(None, description="Residential telephone number")


class BankDetails(BaseModel):
    bank_name: Optional[str] = Field(None, description="Name of the bank")
    branch_name: Optional[str] = Field(None, description="Branch name")
    branch_address: Optional[str] = Field(None, description="Branch address")
    account_number: Optional[str] = Field(None, description="Bank account number — preserve exactly as written")
    account_type: Optional[str] = Field(None, description="Account type (e.g. Savings, Current) — use selections section")
    micr_code: Optional[str] = Field(None, description="MICR code — preserve exactly as written")
    ifsc_code: Optional[str] = Field(None, description="IFSC code — preserve exactly as written")
    internet_banking_enabled: Optional[bool] = Field(None, description="Whether internet banking is enabled — use selections section")
    proof_of_bank: Optional[str] = Field(None, description="Document submitted as proof of bank account")


class FinancialInformation(BaseModel):
    gross_annual_income: Optional[str] = Field(None, description="Gross annual income range or value — use selections section")
    net_worth: Optional[str] = Field(None, description="Net worth value")
    net_worth_date: Optional[str] = Field(None, description="Date as of which net worth is stated — preserve as written")
    occupation: Optional[str] = Field(None, description="Occupation — use selections section")
    other_income_source: Optional[str] = Field(None, description="Other source of income if specified")
    pep_status: Optional[bool] = Field(None, description="Whether applicant is a Politically Exposed Person — use selections section")
    related_to_pep: Optional[bool] = Field(None, description="Whether applicant is related to a PEP — use selections section")
    other_information: Optional[str] = Field(None, description="Any other financial information provided")


class DepositoryDetails(BaseModel):
    depository_name: Optional[str] = Field(None, description="Depository name (CDSL / NSDL)")
    dp_id: Optional[str] = Field(None, description="DP ID — preserve exactly as written")
    beneficiary_id: Optional[str] = Field(None, description="Beneficiary ID / Client ID")
    beneficiary_name: Optional[str] = Field(None, description="Name of the beneficiary account holder")
    second_holder_name: Optional[str] = Field(None, description="Second holder name in the demat account")
    third_holder_name: Optional[str] = Field(None, description="Third holder name in the demat account")
    proof_of_dp: Optional[str] = Field(None, description="Document submitted as proof of depository account")


class TradingPreferences(BaseModel):
    exchange_segments: Optional[List[str]] = Field(default_factory=list, description="Selected exchange segments (e.g. NSE CM, BSE CM) — use selections section")
    commodity_segments: Optional[List[str]] = Field(default_factory=list, description="Selected commodity segments — use selections section")
    internet_trading: Optional[bool] = Field(None, description="Whether internet trading is enabled — use selections section")
    mobile_trading: Optional[bool] = Field(None, description="Whether mobile trading is enabled — use selections section")
    communication_mode: Optional[str] = Field(None, description="Preferred communication mode — use selections section")
    years_in_stocks: Optional[str] = Field(None, description="Years of experience in stocks/equity")
    years_in_derivatives: Optional[str] = Field(None, description="Years of experience in derivatives")
    years_in_commodities: Optional[str] = Field(None, description="Years of experience in commodities")
    years_in_other_investments: Optional[str] = Field(None, description="Years of experience in other investments")
    no_prior_experience: Optional[bool] = Field(None, description="Whether applicant has no prior trading experience — use selections section")
    equity_trading_preference: Optional[List[str]] = Field(default_factory=list, description="Equity trading preferences — use selections section")
    derivative_trading_preference: Optional[List[str]] = Field(default_factory=list, description="Derivative trading preferences — use selections section")
    educational_qualification: Optional[str] = Field(None, description="Educational qualification — use selections section")


class GSTDetails(BaseModel):
    gst_number: Optional[str] = Field(None, description="GST registration number")
    gst_location: Optional[str] = Field(None, description="GST registered location/state")
    gst_validity_date: Optional[str] = Field(None, description="GST validity date — preserve as written")


class MoneyLaunderingInformation(BaseModel):
    fund_source: Optional[str] = Field(None, description="Source of funds")
    non_profit_organization: Optional[bool] = Field(None, description="Whether applicant is associated with a non-profit organization — use selections section")
    past_actions: Optional[str] = Field(None, description="Details of any past regulatory/legal actions")


class OtherStockBrokerDetails(BaseModel):
    stock_broker_name: Optional[str] = Field(None, description="Name of other stock broker")
    client_code: Optional[str] = Field(None, description="Client code with other broker")
    authorized_person: Optional[str] = Field(None, description="Authorized person name")
    exchange: Optional[str] = Field(None, description="Exchange")
    pending_disputes: Optional[bool] = Field(None, description="Whether there are pending disputes with other broker — use selections section")


class AuthorizedPersonDetails(BaseModel):
    registration_number: Optional[str] = Field(None, description="SEBI/Exchange registration number of authorized person")
    authorized_person_name: Optional[str] = Field(None, description="Name of authorized person")
    registered_office_address: Optional[str] = Field(None, description="Registered office address")
    website: Optional[str] = Field(None, description="Website URL")
    phone_number: Optional[str] = Field(None, description="Phone number")
    fax_number: Optional[str] = Field(None, description="Fax number")


class IntroducerDetails(BaseModel):
    introducer_name: Optional[str] = Field(None, description="Full name of the introducer")
    introducer_address: Optional[str] = Field(None, description="Address of the introducer")
    introducer_status: Optional[str] = Field(None, description="Status: Remisier, Authorised Person, Existing Client, or Others — use selections section")
    introducer_phone: Optional[str] = Field(None, description="Phone number of the introducer")
    introducer_signature_present: Optional[bool] = Field(None, description="Whether introducer signature is present — use signatures section")


class FATCADeclaration(BaseModel):
    country_of_birth_outside_india: Optional[bool] = Field(None, description="Country of birth is outside India — map Yes→true, No→false, use selections section")
    tax_resident_outside_india: Optional[bool] = Field(None, description="Tax resident in jurisdictions outside India — map Yes→true, No→false, use selections section")
    citizenship_other_than_india: Optional[bool] = Field(None, description="Holds citizenship of any country other than India — map Yes→true, No→false, use selections section")
    foreign_address_or_phone: Optional[bool] = Field(None, description="Has address or telephone number outside India — map Yes→true, No→false, use selections section")


class RunningAccountAuthorization(BaseModel):
    authorized: Optional[bool] = Field(None, description="Whether applicant authorizes maintaining a running account — use selections section")
    settlement_frequency: Optional[str] = Field(None, description="Settlement frequency if authorized: Monthly or Quarterly — use selections section")


class OfficeUse(BaseModel):
    organization_name: Optional[str] = Field(None, description="Organization name filled by office")
    employee_name: Optional[str] = Field(None, description="Employee name")
    employee_designation: Optional[str] = Field(None, description="Employee designation")
    employee_code: Optional[str] = Field(None, description="Employee code")
    ipv_date: Optional[str] = Field(None, description="In-Person Verification date — preserve as written")
    pan_verification_date: Optional[str] = Field(None, description="PAN verification date — preserve as written")
    amc_code: Optional[str] = Field(None, description="AMC code")
    cersai_code: Optional[str] = Field(None, description="CERSAI code")
    employee_signature_present: Optional[bool] = Field(None, description="Whether employee signature is present — use signatures section")


class AadhaarDocument(BaseModel):
    masked_number: Optional[str] = Field(None, description="Masked Aadhaar number as printed")
    name: Optional[str] = Field(None, description="Name as on Aadhaar")
    date_of_birth: Optional[str] = Field(None, description="Date of birth as on Aadhaar — preserve as written")
    gender: Optional[str] = Field(None, description="Gender as on Aadhaar")
    care_of: Optional[str] = Field(None, description="Care of (C/O) field on Aadhaar")
    address: Optional[str] = Field(None, description="Full address on Aadhaar")
    landmark: Optional[str] = Field(None, description="Landmark on Aadhaar address")
    locality: Optional[str] = Field(None, description="Locality on Aadhaar address")
    city: Optional[str] = Field(None, description="City on Aadhaar address")
    district: Optional[str] = Field(None, description="District on Aadhaar address")
    state: Optional[str] = Field(None, description="State on Aadhaar address")
    pin_code: Optional[str] = Field(None, description="PIN code on Aadhaar address")
    generation_date: Optional[str] = Field(None, description="Aadhaar generation date — preserve as written")
    download_date: Optional[str] = Field(None, description="Aadhaar download date — preserve as written")


class SupportingDocuments(BaseModel):
    aadhaar: Optional[AadhaarDocument] = Field(None, description="Aadhaar document details if submitted")


class IndividualAccountOpeningData(BaseModel):
    """
    Structured extraction output for MOFSL Individual Account Opening form.

    Sections align with the physical document layout. Each section is Optional
    so that the LLM never fails validation when a section is absent from the form.
    """
    form_details: Optional[FormDetails] = Field(default_factory=FormDetails)
    personal_details: Optional[PersonalDetails] = Field(default_factory=PersonalDetails)
    identity_proof: Optional[IdentityProof] = Field(default_factory=IdentityProof)
    correspondence_address: Optional[Address] = Field(default_factory=Address)
    permanent_address: Optional[PermanentAddress] = Field(default_factory=PermanentAddress)
    contact_details: Optional[ContactDetails] = Field(default_factory=ContactDetails)
    bank_details: Optional[BankDetails] = Field(default_factory=BankDetails)
    financial_information: Optional[FinancialInformation] = Field(default_factory=FinancialInformation)
    depository_details: Optional[DepositoryDetails] = Field(default_factory=DepositoryDetails)
    trading_preferences: Optional[TradingPreferences] = Field(default_factory=TradingPreferences)
    gst_details: Optional[GSTDetails] = Field(default_factory=GSTDetails)
    money_laundering_information: Optional[MoneyLaunderingInformation] = Field(default_factory=MoneyLaunderingInformation)
    other_stock_broker_details: Optional[OtherStockBrokerDetails] = Field(default_factory=OtherStockBrokerDetails)
    authorized_person_details: Optional[AuthorizedPersonDetails] = Field(default_factory=AuthorizedPersonDetails)
    introducer_details: Optional[IntroducerDetails] = Field(default_factory=IntroducerDetails)
    fatca_declaration: Optional[FATCADeclaration] = Field(default_factory=FATCADeclaration)
    running_account_authorization: Optional[RunningAccountAuthorization] = Field(default_factory=RunningAccountAuthorization)
    office_use: Optional[OfficeUse] = Field(default_factory=OfficeUse)
    supporting_documents: Optional[SupportingDocuments] = Field(default_factory=SupportingDocuments)
