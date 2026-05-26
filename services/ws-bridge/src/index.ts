import { Kafka } from "kafkajs";
import { config } from "./config";
import { update as updateSnapshot, deviceCount, pointCount } from "./snapshot";
import { createWsServer } from "./server";

async function main() {
  // Kafka consumer — feed snapshot store
  const kafka = new Kafka({
    clientId: "ws-bridge",
    brokers: config.kafkaBrokers,
    retry: { retries: 10 },
  });

  const consumer = kafka.consumer({ groupId: config.kafkaGroupId });

  let retries = 0;
  while (true) {
    try {
      await consumer.connect();
      break;
    } catch (err) {
      retries++;
      const wait = Math.min(2 ** retries, 30);
      console.warn(`[kafka] connect failed, retry in ${wait}s`, (err as Error).message);
      await new Promise((r) => setTimeout(r, wait * 1000));
    }
  }

  await consumer.subscribe({ topic: config.kafkaTopicRaw, fromBeginning: false });

  consumer.run({
    eachMessage: async ({ message }) => {
      if (!message.value) return;
      try {
        const msg = JSON.parse(message.value.toString()) as Record<string, unknown>;
        updateSnapshot(msg);
      } catch {
        // skip malformed messages
      }
    },
  });

  console.log(`[kafka] consuming ${config.kafkaTopicRaw}`);

  // WebSocket server
  const server = createWsServer();
  server.listen(config.port, () => {
    console.log(`[ws-bridge] listening on :${config.port}`);
  });

  // Status log every 30s
  setInterval(() => {
    console.log(`[snapshot] devices=${deviceCount()} points=${pointCount()}`);
  }, 30_000);

  const shutdown = async (sig: string) => {
    console.log(`${sig} received, shutting down`);
    await consumer.disconnect();
    server.close(() => process.exit(0));
  };
  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT",  () => shutdown("SIGINT"));
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});
