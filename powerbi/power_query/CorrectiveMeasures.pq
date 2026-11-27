let
    Source = Csv.Document(File.Contents(DataFolder & "corrective_measures.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"alert_number", type text}, {"measure_kind", type text}, {"measure_group", type text}, {"measure_category", type text}, {"economic_operator", type text}, {"entry_into_force_date", type date}}, "en-US")
in
    Typed
