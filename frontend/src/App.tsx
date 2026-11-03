import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { EmptyState } from "./components/States";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";
import Login from "./pages/Login";
import OrderDetail from "./pages/OrderDetail";
import Orders from "./pages/Orders";
import Profile from "./pages/Profile";
import Register from "./pages/Register";
import RestaurantMenu from "./pages/RestaurantMenu";
import Restaurants from "./pages/Restaurants";
import StaffOrders from "./pages/StaffOrders";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Restaurants />} />
        <Route path="restaurants/:id" element={<RestaurantMenu />} />
        <Route path="cart" element={<Cart />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="checkout" element={<ProtectedRoute role="customer"><Checkout /></ProtectedRoute>} />
        <Route path="orders" element={<ProtectedRoute role="customer"><Orders /></ProtectedRoute>} />
        <Route path="orders/:id" element={<ProtectedRoute role="customer"><OrderDetail /></ProtectedRoute>} />
        <Route path="profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
        <Route path="staff" element={<ProtectedRoute role="staff"><StaffOrders /></ProtectedRoute>} />
        <Route path="*" element={<EmptyState title="Page not found" action={{ to: "/", label: "Back to restaurants" }}>That page doesn't exist.</EmptyState>} />
      </Route>
    </Routes>
  );
}
