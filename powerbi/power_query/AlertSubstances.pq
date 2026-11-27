let
    Source = Csv.Document(File.Contents(DataFolder & "alert_substances.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"alert_number", type text}, {"substance", type text}, {"mention_order", Int64.Type}, {"confidence", type text}}, "en-US")
in
    Typed
