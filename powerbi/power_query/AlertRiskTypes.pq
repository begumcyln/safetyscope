let
    Source = Csv.Document(File.Contents(DataFolder & "alert_risk_types.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"alert_number", type text}, {"risk_type", type text}}, "en-US")
in
    Typed
