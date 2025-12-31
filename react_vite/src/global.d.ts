declare global {
  interface Document {
    configuration: {
      EDITABLE_ROUTES_URL: string;
      createTaskViewUrl: (id: number) => string;
      copyRouteViewUrl: (id: number) => string;
      permissionListViewUrl: (id: number) => string;
      deleteRouteViewUrl: (id: number) => string;
      createRouteUrl: string;
      is_superuser: boolean;
      STATIC_FILE_LOCATION: string;
      editableRouteUrl: (id: number) => string;
      editRouteViewUrl: (id: number) => string;
    };
  }
}

export {};
