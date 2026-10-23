"""Silver H&M (PySpark): CSV de Bronze -> Parquet tipado, limpio y validado + reporte de calidad.

GCP (Serverless for Apache Spark):
  gcloud dataproc batches submit pyspark pipelines/batch/silver_hm.py --region=us-central1 --version=2.2 \
    -- --raw gs://PROJECT-retail-raw/hm --out gs://PROJECT-retail-lake/silver
Local:
  python pipelines/batch/silver_hm.py --raw data/raw --out data/silver
Ninguna fila se pierde en silencio: lo rechazado va a quarantine/ y se cuenta en el reporte.
"""
import argparse
import json

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StringType, StructField, StructType

TX_SCHEMA = StructType([StructField(c, StringType()) for c in
                        ["t_dat", "customer_id", "article_id", "price", "sales_channel_id"]])


def read_csv(spark, path, schema=None):
    r = spark.read.option("header", True).option("multiLine", True).option("escape", '"')
    return (r.schema(schema) if schema else r.option("inferSchema", False)).csv(path)


def articles(df):
    out = (df.select([F.trim(F.col(c)).alias(c) for c in df.columns])
           .withColumn("detail_desc", F.coalesce("detail_desc", "prod_name"))
           .dropDuplicates(["article_id"]))
    for c in ["product_type_no", "graphical_appearance_no", "colour_group_code", "perceived_colour_value_id",
              "perceived_colour_master_id", "department_no", "index_group_no", "section_no", "garment_group_no"]:
        out = out.withColumn(c, F.col(c).cast("int"))
    return out.withColumn("_ingested_at", F.current_timestamp())


def customers(df):
    age = F.col("age").cast("int")
    # Spark no distingue mayúsculas: renombrar antes para no pisar FN/Active al crear fn/active
    return (df.dropDuplicates(["customer_id"])
            .withColumnRenamed("FN", "_fn").withColumnRenamed("Active", "_active")
            .withColumn("fn", F.coalesce(F.col("_fn").cast("int"), F.lit(0)))
            .withColumn("active", F.coalesce(F.col("_active").cast("int"), F.lit(0)))
            .withColumn("club_member_status", F.coalesce("club_member_status", F.lit("NONE")))
            .withColumn("fashion_news_frequency",
                        F.when(F.upper(F.coalesce("fashion_news_frequency", F.lit("NONE"))) == "NONE", "NONE")
                        .otherwise(F.col("fashion_news_frequency")))
            .withColumn("age", age)
            .withColumn("age_band", F.when(age.isNull(), "sin_edad").when(age < 25, "16-24").when(age < 35, "25-34")
                        .when(age < 45, "35-44").when(age < 55, "45-54").otherwise("55+"))
            .drop("_fn", "_active")
            .withColumn("_ingested_at", F.current_timestamp()))


def transactions(df, arts):
    tx = (df.withColumn("t_dat", F.to_date("t_dat"))
          .withColumn("price", F.col("price").cast("double"))
          .withColumn("sales_channel_id", F.col("sales_channel_id").cast("int"))
          .join(arts.select("article_id", F.lit(True).alias("_art_ok")), "article_id", "left"))
    motivo = (F.when(F.col("t_dat").isNull(), "fecha_invalida")
              .when(F.col("customer_id").isNull(), "sin_cliente")
              .when(F.col("_art_ok").isNull(), "articulo_inexistente")
              .when(F.col("price").isNull() | (F.col("price") <= 0), "precio_invalido")
              .when(~F.col("sales_channel_id").isin(1, 2), "canal_invalido"))
    tx = tx.withColumn("_motivo", motivo).drop("_art_ok")
    # ponytail: no se deduplica; H&M registra una línea por unidad y repetir artículo el mismo día es válido
    ok = (tx.filter(F.col("_motivo").isNull()).drop("_motivo")
          .withColumn("year_month", F.date_format("t_dat", "yyyy-MM"))
          .withColumn("_source_system", F.lit("hm_kaggle"))
          .withColumn("_ingested_at", F.current_timestamp()))
    return ok, tx.filter(F.col("_motivo").isNotNull())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spark = SparkSession.builder.appName("silver_hm").getOrCreate()

    arts_in = read_csv(spark, f"{a.raw}/articles.csv")
    cust_in = read_csv(spark, f"{a.raw}/customers.csv")
    tx_in = read_csv(spark, f"{a.raw}/transactions_train.csv", TX_SCHEMA)

    arts = articles(arts_in).cache()
    cust = customers(cust_in)
    tx_ok, tx_bad = transactions(tx_in, arts)

    arts.write.mode("overwrite").parquet(f"{a.out}/articles")
    cust.write.mode("overwrite").parquet(f"{a.out}/customers")
    tx_ok.write.mode("overwrite").partitionBy("year_month").parquet(f"{a.out}/transactions")
    tx_bad.write.mode("overwrite").parquet(f"{a.out}/quarantine/transactions")

    spark.read.parquet(f"{a.out}/transactions").createOrReplaceTempView("t")
    tx_out = spark.sql("SELECT COUNT(*) n, MIN(t_dat) d0, MAX(t_dat) d1 FROM t").first()
    report = {
        "articles": {"entrada": arts_in.count(), "salida": arts.count(),
                     "desc_imputada": arts_in.filter(F.col("detail_desc").isNull()).count()},
        "customers": {"entrada": cust_in.count(), "salida": spark.read.parquet(f"{a.out}/customers").count(),
                      "edad_nula": cust_in.filter(F.col("age").isNull()).count()},
        "transactions": {"entrada": tx_in.count(), "salida": tx_out["n"], "desde": str(tx_out["d0"]), "hasta": str(tx_out["d1"]),
                         "rechazadas": dict(spark.read.parquet(f"{a.out}/quarantine/transactions")
                                            .groupBy("_motivo").count().rdd.map(tuple).collect())},
    }
    t = report["transactions"]
    t["conciliado"] = t["entrada"] == t["salida"] + sum(t["rechazadas"].values())
    txt = json.dumps(report, indent=2, ensure_ascii=False)
    print(txt)
    spark.createDataFrame([(txt,)], ["r"]).coalesce(1).write.mode("overwrite").text(f"{a.out}/_quality_report")
    assert t["conciliado"], "Las filas de salida + rechazadas no cuadran con la entrada"


if __name__ == "__main__":
    main()
