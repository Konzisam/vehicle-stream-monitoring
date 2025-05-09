from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType, StructField, StringType, TimestampType, DoubleType, IntegerType

from src.config import configuration

from pyspark.sql import SparkSession, DataFrame


def main():
    spark = ((SparkSession.builder.appName('SmartCityStreaming'))
             .config('spark.jars.packages',
                     "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
                     'org.apache.hadoop:hadoop-aws:3.3.4,'
                     'com.amazonaws:aws-java-sdk-bundle:1.12.262')
             .config('spark.hadoop.fs.s3a.impl','org.apache.hadoop.fs.s3a.S3AFileSystem')
             .config('spark.hadoop.fs.s3a.access.key', configuration.get('AWS_ACCESS_KEY'))
             .config('spark.hadoop.fs.s3a.secret.key', configuration.get('AWS_SECRET_KEY'))
             .config('spark.hadoop.fs.s3a.aws.credentials.provider',
                     'org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider')
             .config('spark.hadoop.fs.s3a.endpoint', 's3.amazonaws.com')
             .getOrCreate())

    # Adjust log level to minimize console output on executors
    spark.sparkContext.setLogLevel('WARN')

    vehicle_schema = StructType([
        StructField("id", StringType(), True),
        StructField("device_Id", StringType(), True),
        StructField("timestamp", TimestampType(), True),
        StructField("location", StringType(), True),
        StructField("speed", DoubleType(), True),
        StructField("direction", StringType(), True),
        StructField("make", StringType(), True),
        StructField("model", StringType(), True),
        StructField("year", IntegerType(), True),
        StructField("fuelType", StringType(), True)
    ])

    gps_schema = StructType([
        StructField("id", StringType(), True),
        StructField("deviceId", StringType(), True),
        StructField("timestamp", TimestampType(), True),
        StructField("speed", DoubleType(), True),
        StructField("direction", StringType(), True),
        StructField("vehicleType", StringType(), True)
    ])

    traffic_schema = StructType([
        StructField("id", StringType(), True),
        StructField("deviceId", StringType(), True),
        StructField("cameraId", StringType(), True),
        StructField("timestamp", TimestampType(), True),
        StructField("location", StringType(), True),
        StructField("snapshot", StringType(), True)
    ])

    weather_schema = StructType([
        StructField("id", StringType(), True),
        StructField("deviceId", StringType(), True),
        StructField("location", StringType(), True),
        StructField("timestamp", TimestampType(), True),
        StructField("temperature", DoubleType(), True),
        StructField("weatherCondition", StringType(), True),
        StructField("precipitation", DoubleType(), True),
        StructField("windSpeed", DoubleType(), True),
        StructField("humidity", IntegerType(), True),
        StructField("airQualityIndex", DoubleType(), True)
    ])

    emergency_schema = StructType([
        StructField("id", StringType(), True),
        StructField("deviceId", StringType(), True),
        StructField("incidentId", StringType(), True),
        StructField("type", StringType(), True),
        StructField("timestamp", TimestampType(), True),
        StructField("location", StringType(), True),
        StructField("status", StringType(), True),
        StructField("description", StringType(), True)
    ])

    def read_kafka_topic(topic, schema):
        return (spark.readStream
                .format('kafka')
                .option('kafka.bootstrap.servers', 'broker:29092')
                .option('subscribe', topic)
                .option('startingOffsets', 'earliest')
                .load()
                .selectExpr('CAST(value as STRING)')
                .select(from_json(col('value'), schema).alias('data'))
                .select('data.*')
                .withWatermark('timestamp', delayThreshold='2 minutes'))

    def streamWriter(input: DataFrame, checkpointFolder, output):
            return (input.writeStream
                     .format('parquet')
                     .option('checkpointLocation', checkpointFolder)
                     .option('path', output)
                     .outputMode('append')
                    # .trigger(processingTime='4 minute')
                     .start())


    vehicleDF = read_kafka_topic('vehicle_data', vehicle_schema).alias('vehicle')
    gpsDF = read_kafka_topic('gps_data', gps_schema).alias('gps')
    trafficDF = read_kafka_topic('traffic_data', traffic_schema).alias('traffic')
    weatherDF = read_kafka_topic('weather_data', weather_schema).alias('weather')
    emergencyDF = read_kafka_topic('emergency_data', emergency_schema).alias('emergency')

    print(vehicleDF.isStreaming)
    vehicleDF.printSchema()

    query1 = streamWriter(vehicleDF, 's3a://streaming-spark/checkpoints/vehicle_data',
                 's3a://streaming-spark/data/vehicle_data')

    query2 = streamWriter(gpsDF, 's3a://streaming-spark/checkpoints/gps_data',
                 's3a://streaming-spark/data/gps_data')
    query3 = streamWriter(trafficDF, 's3a://streaming-spark/checkpoints/traffic_data',
                 's3a://streaming-spark/data/traffic_data')
    query4 = streamWriter(weatherDF, 's3a://streaming-spark/checkpoints/weather_data',
                 's3a://streaming-spark/data/weather_data')
    query5 = streamWriter(emergencyDF, 's3a://streaming-spark/checkpoints/emergency_data',
                 's3a://streaming-spark/data/emergency_data')

    queries = [query1, query2, query3, query4, query5]
    for query in queries:
        query.awaitTermination()

if __name__ == "__main__":
    main()
