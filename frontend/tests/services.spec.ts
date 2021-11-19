import "pinia";
import { createApp, markRaw } from "vue";
import { setActivePinia, createPinia } from "pinia";
import { useServices, createService } from "../src/stores/service";
import { Client } from "../src/typings";
import { createClient } from "../src/client";

declare module "pinia" {
  export interface PiniaCustomProperties {
    client: Client;
    logMessages: boolean;
    messages: any[];
  }
}

class Connection {
  onmessage = (message: any) => {};
  send = (message: MessageEvent) => {
    this.onmessage(message);
  };
}

function createEvent(data: any): MessageEvent {
  return { data: JSON.stringify(data) } as MessageEvent;
}

let client: Client;
let connection: Connection;
let serviceStore: any;

describe("Services Store Websocket", () => {
  beforeEach(() => {
    const app = createApp({});
    client = createClient();
    connection = new Connection();
    client.connection = connection;
    client.registerWebsocketConnectionCallbacks(client.connection);
    const pinia = createPinia().use(({ store }) => {
      store.client = markRaw(client);
      store.logMessages = true;
      store.messages = [];
    });
    app.use(pinia);
    setActivePinia(pinia);
    serviceStore = useServices();
  });

  it("has no store registered", () => {
    connection.send(createEvent({ foo: "bar" }));
    expect(serviceStore.messages).toEqual([]);
  });

  it("has a store registered", () => {
    client.registerStore(serviceStore);
    const payload = { foo: "bar" };
    connection.send(createEvent(payload));
    expect(serviceStore.messages[0]).toStrictEqual(payload);
  });

  it("received create or update service", () => {
    client.registerStore(serviceStore);
    const service = {
      id: 1,
      name: "fastdeploy",
      collect: "collect.py",
      deploy: "deploy.sh",
      deleted: false,
    };
    const payload = {
      ...service,
      type: "service",
    };
    connection.send(createEvent(payload));
    expect(serviceStore.messages[0]).toStrictEqual(payload);
    expect(serviceStore.services.get(1)).toStrictEqual(service);
  });

  it("received delete service", () => {
    client.registerStore(serviceStore);
    const service = {
      id: 1,
      name: "fastdeploy",
      collect: "collect.py",
      deploy: "deploy.sh",
      deleted: false,
    };
    serviceStore.services.set(1, service);
    const payload = {
      ...service,
      type: "service",
      deleted: true,
    };
    connection.send(createEvent(payload));
    expect(serviceStore.messages[0]).toStrictEqual(payload);
    expect(serviceStore.services.size).toBe(0);
  });

  it("adds a service to the store", () => {
    client.registerStore(serviceStore);
    const payload = { foo: "bar" };
    connection.send(createEvent(payload));
    expect(serviceStore.messages[0]).toStrictEqual(payload);
  });
});


function createAddServiceClient() {
  // replace one addService function from original client
  // with dummy one
  const client = createClient();
  client.addService = async (service: any) => {
    console.log("add service in dummy client: ", service);
    return { ...service, id: 1 };
  };
  return client;
}

describe("Services Store Actions", () => {
  beforeEach(() => {
    const app = createApp({});
    client = createAddServiceClient()
    const pinia = createPinia().use(({ store }) => {
      store.client = markRaw(client);
    });
    app.use(pinia);
    setActivePinia(pinia);
    serviceStore = useServices();
  });

  it("adds a service to the store", async () => {
    const service = createService({
      name: "fastdeploy",
      collect: "collect.py",
      deploy: "deploy.sh",
    });
    await serviceStore.addService(service);
    expect(serviceStore.services.get(1)).toStrictEqual({ ...service, id: 1 });
  });
});
