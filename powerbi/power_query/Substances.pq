let
    Source = Csv.Document(File.Contents(DataFolder & "substances.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"substance", type text}, {"abbreviation", type text}, {"agent_type", type text}, {"substance_group", type text}, {"cas_number", type text}, {"substance_label", type text}}, "en-US")
in
    Typed
