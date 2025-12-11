import React, { useState, useEffect } from 'react';
import { Trash2, Copy, X } from 'lucide-react';
import { useAuth } from './AuthComponents';

const PasswordModal = ({ password, onClose }) => {
  const copyToClipboard = () => {
    navigator.clipboard.writeText(password);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg shadow-xl w-96">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium">Generated Password</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex items-center space-x-2 p-2 bg-gray-50 rounded">
          <code className="flex-1">{password}</code>
          <button onClick={copyToClipboard} className="p-1 hover:bg-gray-200 rounded">
            <Copy className="w-4 h-4" />
          </button>
        </div>
        <p className="mt-4 text-sm text-gray-600">Please save this password. It won't be shown again.</p>
      </div>
    </div>
  );
};

export const AdminModal = ({ setShowAdmin, serverUrl }) => {
  const [users, setUsers] = useState([]);
  const [newUser, setNewUser] = useState({ username: '', fullName: '', email: '' });
  const [generatedPassword, setGeneratedPassword] = useState(null);
  const { authFetch } = useAuth();

  // Fetch users when modal opens
  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await authFetch(`${serverUrl}/users`);
        if (response.ok) {
          const data = await response.json();
          setUsers(data);
        }
      } catch (error) {
        console.error('Error fetching users:', error);
      }
    };

    fetchUsers();
  }, [authFetch, serverUrl]); // Only runs once when modal opens

  const handleDeleteUser = async (username) => {
    try {
      const response = await authFetch(`${serverUrl}/users/${username}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        // Update the users list by filtering out the deleted user
        setUsers(users.filter((user) => user.username !== username));
      }
    } catch (error) {
      console.error('Error deleting user:', error);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    try {
      const response = await authFetch(`${serverUrl}/users`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: newUser.username,
          full_name: newUser.fullName,
          email: newUser.email,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setGeneratedPassword(data.password);
        setNewUser({ username: '', fullName: '', email: '' });
        // Add the new user to the list
        const newUserData = {
          username: newUser.username,
          full_name: newUser.fullName,
          email: newUser.email,
        };
        setUsers((prevUsers) => [...prevUsers, newUserData]);
      }
    } catch (error) {
      console.error('Error creating user:', error);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
      <div className="bg-white p-6 w-[800px] max-h-[90vh] flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium">User Administration</h3>
          <button onClick={() => setShowAdmin(false)} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-auto mb-6">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Username
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Full Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Email
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {users.map((user) => (
                <tr key={user.username}>
                  <td className="px-6 py-4 whitespace-nowrap">{user.username}</td>
                  <td className="px-6 py-4 whitespace-nowrap">{user.full_name}</td>
                  <td className="px-6 py-4 whitespace-nowrap">{user.email}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <button onClick={() => handleDeleteUser(user.username)} className="text-red-600 hover:text-red-900">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="border-t pt-4">
          <h4 className="text-md font-medium mb-4">Create New User</h4>
          <form onSubmit={handleCreateUser} className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                <input
                  type="text"
                  required
                  value={newUser.username}
                  onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={newUser.fullName}
                  onChange={(e) => setNewUser({ ...newUser, fullName: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email (optional)</label>
                <input
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md"
              >
                Create User
              </button>
            </div>
          </form>
        </div>
      </div>

      {generatedPassword && <PasswordModal password={generatedPassword} onClose={() => setGeneratedPassword(null)} />}
    </div>
  );
};

export default AdminModal;
