let
    Source = Csv.Document(File.Contents(DataFolder & "alerts.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"alert_number", type text}, {"case_url", type text}, {"alert_level", type text}, {"user_type", type text}, {"notifying_country", type text}, {"origin_country", type text}, {"origin_region", type text}, {"product_type", type text}, {"product_group", type text}, {"product_name", type text}, {"brand", type text}, {"risk_type", type text}, {"primary_substance", type text}, {"weekly_report", type text}, {"weekly_report_date", type date}, {"publication_date", type date}, {"first_measure_date", type date}, {"days_measure_to_report", Int64.Type}, {"based_on_ingredient_list", type logical}, {"has_measured_value", type logical}, {"counterfeit", type text}, {"alert_number_year", Int64.Type}}, "en-US")
in
    Typed
